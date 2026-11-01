# Cloud Data Warehouse & Analytics | Python, BigQuery, dbt

**Project type:** Independent demonstration using public weather API data and sample fixtures.

Built a reproducible ELT workflow that extracts historical daily weather observations from Open-Meteo, validates data with Python, and performs idempotent loads into partitioned and clustered BigQuery tables. dbt staging and monthly analytics models transform the raw data into reporting-ready metrics. Included quality tests, GitHub Actions CI, Docker and local demo mode that does not require cloud credentials.

**Stack:** Python, Google BigQuery, dbt, SQL, GCP, Docker, GitHub Actions.

**Deliverables:** Ingestion package, incremental upsert design, staging/mart SQL models, data tests, sample data, developer instructions.

**Note:** Public sample data and synthetic demonstration fixtures; no client engagement is claimed.
