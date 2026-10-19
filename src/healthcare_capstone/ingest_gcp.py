"""Upload one generated batch to GCS and load its tables into BigQuery.

The optional Google Cloud SDK packages are imported inside the entry point so
local generation and tests remain dependency-free.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from healthcare_capstone.generator import (
    CLAIM_FIELDS,
    ENCOUNTER_FIELDS,
    EVENT_FIELDS,
    PATIENT_FIELDS,
)

TABLES = ("patients", "encounters", "clinical_events", "claims")
FIELD_NAMES = {
    "patients": PATIENT_FIELDS,
    "encounters": ENCOUNTER_FIELDS,
    "clinical_events": EVENT_FIELDS,
    "claims": CLAIM_FIELDS,
}


def ingest_dataset(
    input_dir: Path,
    project_id: str,
    bucket_name: str,
    dataset_id: str = "healthcare_capstone_raw",
    location: str = "US",
) -> dict[str, Any]:
    """Upload CSVs under an immutable run prefix, then replace raw tables.

    Cloud resources and credentials are intentionally not created here.
    Terraform provisions the bucket and datasets; the caller authenticates with
    Application Default Credentials before running this function.
    """
    try:
        from google.cloud import bigquery, storage
    except ImportError as exc:  # pragma: no cover - requires optional cloud SDK
        raise RuntimeError(
            "Install requirements-gcp.txt to use the GCP ingestion command."
        ) from exc

    manifest_path = input_dir / "data_quality_manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Missing generator manifest: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("synthetic_only") is not True:
        raise ValueError("Refusing to ingest a batch not marked synthetic_only=true")

    files = {name: input_dir / f"{name}.csv" for name in TABLES}
    missing = [str(path) for path in files.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing generated source files: " + ", ".join(missing))

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    prefix = f"synthetic/run_id={run_id}"
    storage_client = storage.Client(project=project_id)
    bucket = storage_client.bucket(bucket_name)
    bigquery_client = bigquery.Client(project=project_id, location=location)

    uris: dict[str, str] = {}
    for table_name, path in files.items():
        object_name = f"{prefix}/{path.name}"
        blob = bucket.blob(object_name)
        blob.upload_from_filename(str(path), content_type="text/csv")
        uris[table_name] = f"gs://{bucket_name}/{object_name}"
    manifest_blob = bucket.blob(f"{prefix}/data_quality_manifest.json")
    manifest_blob.upload_from_filename(str(manifest_path), content_type="application/json")

    loaded_rows: dict[str, int] = {}
    for table_name in TABLES:
        table_id = f"{project_id}.{dataset_id}.{table_name}"
        job_config = bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.CSV,
            skip_leading_rows=1,
            # Keep the raw landing layer lossless and predictable. dbt owns
            # all parsing and safe casts in the typed staging layer.
            schema=[bigquery.SchemaField(name, "STRING") for name in FIELD_NAMES[table_name]],
            autodetect=False,
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
            create_disposition=bigquery.CreateDisposition.CREATE_IF_NEEDED,
        )
        job = bigquery_client.load_table_from_uri(
            uris[table_name], table_id, job_config=job_config, location=location
        )
        job.result()
        loaded_rows[table_name] = bigquery_client.get_table(table_id).num_rows
        expected_rows = manifest["row_counts"][table_name]
        if loaded_rows[table_name] != expected_rows:
            raise RuntimeError(
                f"Row-count mismatch for {table_name}: expected {expected_rows}, "
                f"loaded {loaded_rows[table_name]}"
            )

    return {
        "run_id": run_id,
        "source_prefix": f"gs://{bucket_name}/{prefix}/",
        "row_counts": loaded_rows,
        "manifest_anomalies": manifest.get("injected_data_quality_conditions", {}),
    }
