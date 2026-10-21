# Healthcare Intelligence Platform

A synthetic-data healthcare platform with source code for generation, cloud infrastructure, warehouse transformations, machine learning, and Power BI. See the repository’s build status for implemented components and verified execution results.

> **Safety boundary:** All generated records are synthetic. They do not describe real people and must not be replaced with employer or patient data.

## What this project demonstrates

- Reproducible generation and ingestion of messy healthcare records.
- A GCP foundation with Terraform, BigQuery, and a landing bucket.
- dbt transformations, dimensional models, and data-quality checks.
- Readmission and length-of-stay prediction examples with leakage-aware evaluation.
- Power BI reporting for care outcomes, patient flow, revenue cycle, and pipeline health.
- Clear architecture notes, trade-offs, and operational telemetry.

## Build status
| Phase | Scope | Status |
|---|---|---|
| 1. Data engineering | Synthetic data contract, generator, GCP infrastructure, ingestion, dbt warehouse | Complete |
| 2. Data science | Time-aware features, 30-day readmission and length-of-stay models, observability | Complete |
| 3. BI development | Clinical, operational, financial, and pipeline-health Power BI hub | Complete |
| 4. Case study | Architecture, trade-offs, runbook, and portfolio narrative | Complete |

## Quick start: generate the synthetic source data

Requires Python 3.10 or later. The generator uses only the Python standard library.

```bash
python -m pip install -e .
python -m healthcare_capstone.cli generate --output data/generated --patients 500 --seed 42
```

The command writes four CSV files and a manifest:

- `patients.csv`
- `encounters.csv`
- `clinical_events.csv`
- `claims.csv`
- `data_quality_manifest.json`

The generated event stream deliberately includes late and out-of-order arrivals, missing event timestamps, null department values, and repeated source event keys. The manifest records the injected conditions so they can be distinguished from accidental defects.

## Optional GCP ingestion

After applying the reviewed Terraform plan and authenticating with Application Default Credentials, install `requirements-gcp.txt`, then run:

```bash
export GCP_PROJECT_ID="your-gcp-project-id"
export DBT_RAW_DATASET="healthcare_capstone_raw"
export DBT_ANALYTICS_DATASET="healthcare_capstone_analytics"
python -m healthcare_capstone.cli ingest-gcp \
  --project-id "$GCP_PROJECT_ID" \
  --bucket "your-terraform-output-bucket" \
  --dataset "$DBT_RAW_DATASET"
```

The ingestion command refuses a batch without a synthetic-only manifest, writes each run to an immutable GCS prefix, loads the four raw tables, and checks BigQuery row counts against the manifest. Each accepted batch replaces the current raw snapshot; this is a portfolio/demo workflow, not a multi-tenant production ingest service.

## Project layout

```text
src/healthcare_capstone/   deterministic synthetic data generator
tests/                     unit tests for data and anomaly contracts
infra/terraform/           GCP bucket, BigQuery dataset, and service account
warehouse/                 dbt project and BigQuery models
docs/                      architecture and engineering decisions
data/generated/            local generated data (git-ignored)
```

## Intended data flow

1. Generate synthetic source records and validate their schema and manifest.
2. Land immutable CSV batches in Cloud Storage with a run identifier.
3. Load raw tables into BigQuery and retain ingestion metadata.
4. Use dbt to stage, deduplicate, test, and model encounter and event data.
5. Build time-safe features and persist model scores with model/run metadata.
6. Serve shared marts to Power BI, including pipeline freshness and quality.

The local generator and tests can run without a GCP account. Cloud provisioning and warehouse execution will require a GCP project, billing enabled, and local credentials before deployment. For dbt, copy `warehouse/profiles.example.yml` to `~/.dbt/profiles.yml`, then set the documented environment variables.

## Development

```bash
python -m unittest discover -s tests -v
```

See [`docs/architecture.md`](docs/architecture.md) and [`docs/decisions.md`](docs/decisions.md) for the initial system boundaries and trade-offs.
See [`docs/data-contract.md`](docs/data-contract.md) for source table grains, keys, and intentional edge cases.
