import json
from pathlib import Path
from unittest.mock import Mock
import pytest
from cloud_warehouse.pipeline import CITIES, fetch_city, normalize, validate_dates, write_ndjson


def test_fixtures_normalize():
    for city in CITIES:
        payload = json.loads((Path(__file__).parents[1] / "fixtures" / f"{city}.json").read_text())
        rows = normalize(city, payload)
        assert len(rows) == 3
        assert rows[0]["city"] == city


def test_dates_reversed():
    with pytest.raises(ValueError):
        validate_dates("2024-02-01", "2024-01-01")


def test_missing_column_rejected():
    with pytest.raises(ValueError, match="Missing"):
        normalize("kyiv", {"daily": {"time": ["2024-01-01"]}})


def test_temperature_inversion_rejected():
    payload = {"daily": {"time": ["2024-01-01"], "temperature_2m_max": [0], "temperature_2m_min": [5], "precipitation_sum": [0]}}
    with pytest.raises(ValueError, match="Invalid temperatures"):
        normalize("kyiv", payload)


def test_ndjson(tmp_path):
    target = tmp_path / "a" / "data.ndjson"
    write_ndjson([{"city": "kyiv", "observation_date": "2024-01-01"}], target)
    assert json.loads(target.read_text().strip())["city"] == "kyiv"


def test_request_parameters_and_timeout():
    session = Mock()
    session.get.return_value.json.return_value = {"daily": {}}
    fetch_city("kyiv", "2024-01-01", "2024-01-02", session=session)
    assert session.get.call_args.kwargs["timeout"] == 45
    assert session.get.call_args.kwargs["params"]["timezone"] == "UTC"
