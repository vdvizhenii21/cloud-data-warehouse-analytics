"""Reproducible historical weather observations for three cities."""
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import requests

CITIES = {
    "kyiv": (50.4501, 30.5234),
    "london": (51.5072, -0.1276),
    "new_york": (40.7128, -74.0060),
}
MEASURES = ("temperature_2m_max", "temperature_2m_min", "precipitation_sum")
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def validate_dates(start: str, end: str) -> None:
    if date.fromisoformat(start) > date.fromisoformat(end):
        raise ValueError("start date must not be after end date")
    if date.fromisoformat(end) >= date.today():
        raise ValueError("end date must be before today for complete historical days")


def fetch_city(city: str, start: str, end: str, session: Any = requests) -> dict:
    if city not in CITIES:
        raise ValueError(f"Unknown city: {city}")
    lat, lon = CITIES[city]
    response = session.get(ARCHIVE_URL, params={
        "latitude": lat, "longitude": lon,
        "start_date": start, "end_date": end,
        "daily": ",".join(MEASURES), "timezone": "UTC",
    }, timeout=45)
    response.raise_for_status()
    return response.json()


def normalize(city: str, payload: dict) -> list[dict]:
    daily = payload.get("daily", {})
    dates = daily.get("time", [])
    for key in MEASURES:
        if len(daily.get(key, [])) != len(dates):
            raise ValueError(f"Missing or mismatched {key} data for {city}")
    if len(dates) != len(set(dates)):
        raise ValueError(f"Duplicate dates for {city}")
    rows = []
    for i, day in enumerate(dates):
        date.fromisoformat(day)
        record = {"city": city, "observation_date": day}
        for key in MEASURES:
            value = daily[key][i]
            record[key] = None if value is None else float(value)
        if (record["temperature_2m_max"] is not None and
            record["temperature_2m_min"] is not None and
            record["temperature_2m_max"] < record["temperature_2m_min"]):
            raise ValueError(f"Invalid temperatures: {city} {day}")
        if record["precipitation_sum"] is not None and record["precipitation_sum"] < 0:
            raise ValueError(f"Negative precipitation: {city} {day}")
        rows.append(record)
    return rows


def write_ndjson(rows: list[dict], target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_to_bigquery(rows: list[dict], project: str, dataset: str) -> None:
    """Load a temporary table and MERGE by natural key (city, observation_date)."""
    from google.cloud import bigquery

    if not IDENTIFIER.fullmatch(project.replace("-", "_")) or not IDENTIFIER.fullmatch(dataset):
        raise ValueError("Invalid BigQuery project/dataset identifier")
    client = bigquery.Client(project=project)
    dataset_id = f"{project}.{dataset}"
    client.create_dataset(bigquery.Dataset(dataset_id), exists_ok=True)
    target = f"{dataset_id}.raw_weather_daily"
    schema = [
        bigquery.SchemaField("city", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("observation_date", "DATE", mode="REQUIRED"),
        *[bigquery.SchemaField(col, "FLOAT") for col in MEASURES],
    ]
    table = bigquery.Table(target, schema=schema)
    table.time_partitioning = bigquery.TimePartitioning(field="observation_date")
    table.clustering_fields = ["city"]
    client.create_table(table, exists_ok=True)
    stage = f"{dataset_id}._weather_stage_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
    config = bigquery.LoadJobConfig(schema=schema, write_disposition="WRITE_TRUNCATE", source_format="NEWLINE_DELIMITED_JSON")
    from io import BytesIO
    payload = "".join(json.dumps(row) + "\n" for row in rows).encode("utf-8")
    if not rows:
        print("No rows, skipping load")
        return
    try:
        client.load_table_from_file(BytesIO(payload), stage, job_config=config).result()
        cols = ", ".join(MEASURES)
        assignments = ", ".join(f"T.{name} = S.{name}" for name in MEASURES)
        client.query(f"""
            MERGE `{target}` T USING `{stage}` S
            ON T.city = S.city AND T.observation_date = S.observation_date
            WHEN MATCHED THEN UPDATE SET {assignments}
            WHEN NOT MATCHED THEN INSERT (city, observation_date, {cols})
            VALUES (S.city, S.observation_date, {', '.join('S.' + name for name in MEASURES)})
        """).result()
    finally:
        client.delete_table(stage, not_found_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="2024-01-01")
    parser.add_argument("--end", default="2024-01-31")
    parser.add_argument("--source", choices=["api", "fixture"], default="fixture")
    parser.add_argument("--sink", choices=["local", "bigquery"], default="local")
    parser.add_argument("--output", default="output/weather_daily.ndjson")
    args = parser.parse_args()
    validate_dates(args.start, args.end)
    rows = []
    for city in CITIES:
        if args.source == "fixture":
            payload = json.loads((Path(__file__).parents[2] / "fixtures" / f"{city}.json").read_text())
        else:
            payload = fetch_city(city, args.start, args.end)
        normalized = normalize(city, payload)
        rows.extend(row for row in normalized if args.start <= row["observation_date"] <= args.end)
    if len(rows) != len({(r["city"], r["observation_date"]) for r in rows}):
        raise ValueError("Duplicate natural key")
    if args.sink == "local":
        write_ndjson(rows, Path(args.output))
        print(f"Wrote {len(rows)} rows to {args.output}")
    else:
        project, dataset = os.environ.get("GCP_PROJECT_ID"), os.getenv("BQ_DATASET", "weather_analytics")
        if not project:
            parser.error("GCP_PROJECT_ID must be set for BigQuery sink")
        load_to_bigquery(rows, project, dataset)
        print(f"Merged {len(rows)} rows into {project}.{dataset}.raw_weather_daily")


if __name__ == "__main__":
    main()
