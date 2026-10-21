"""Upload one generated batch to GCS and load its tables into BigQuery atomically.

The optional Google Cloud SDK packages are imported inside the entry point so
local generation and tests remain dependency-free.
"""

from __future__ import annotations

import json
import time
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


def _record_ingestion_run(
    bigquery_client: Any,
    project_id: str,
    dataset_id: str,
    run_record: dict[str, Any],
) -> None:
    """Persist an audit row in BigQuery _ingestion_runs for operational tracking."""
    from google.cloud import bigquery

    runs_table_id = f"{project_id}.{dataset_id}._ingestion_runs"
    schema = [
        bigquery.SchemaField("run_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("status", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("started_at", "TIMESTAMP", mode="REQUIRED"),
        bigquery.SchemaField("completed_at", "TIMESTAMP", mode="NULLABLE"),
        bigquery.SchemaField("duration_seconds", "FLOAT64", mode="NULLABLE"),
        bigquery.SchemaField("source_prefix", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("row_counts_json", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("error_message", "STRING", mode="NULLABLE"),
    ]
    table = bigquery.Table(runs_table_id, schema=schema)
    bigquery_client.create_table(table, exists_ok=True)

    errors = bigquery_client.insert_rows_json(runs_table_id, [run_record])
    if errors:
        # Insertion into audit log should warn rather than mask the underlying pipeline status
        print(f"Warning: failed to record ingestion audit row: {errors}")


def ingest_dataset(
    input_dir: Path,
    project_id: str,
    bucket_name: str,
    dataset_id: str = "healthcare_capstone_raw",
    location: str = "US",
) -> dict[str, Any]:
    """Upload CSVs and atomically publish to BigQuery.

    Uses staging tables to prevent partially loaded runs from appearing
    complete, and logs execution to _ingestion_runs. Safe to retry.
    """
    try:
        from google.cloud import bigquery, storage
    except ImportError as exc:
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

    start_time = time.time()
    started_at = datetime.now(timezone.utc)
    run_id = started_at.strftime("%Y%m%dT%H%M%SZ")
    prefix = f"synthetic/run_id={run_id}"

    storage_client = storage.Client(project=project_id)
    bucket = storage_client.bucket(bucket_name)
    bigquery_client = bigquery.Client(project=project_id, location=location)

    # 1. Upload files to immutable cloud storage prefix
    uris: dict[str, str] = {}
    for table_name, path in files.items():
        object_name = f"{prefix}/{path.name}"
        blob = bucket.blob(object_name)
        blob.upload_from_filename(str(path), content_type="text/csv")
        uris[table_name] = f"gs://{bucket_name}/{object_name}"
    manifest_blob = bucket.blob(f"{prefix}/data_quality_manifest.json")
    manifest_blob.upload_from_filename(str(manifest_path), content_type="application/json")

    staging_table_ids: dict[str, str] = {}
    loaded_rows: dict[str, int] = {}

    try:
        # 2. Stage each table in an isolated staging table first
        for table_name in TABLES:
            staging_table_name = f"{table_name}__staging_{run_id}"
            staging_table_id = f"{project_id}.{dataset_id}.{staging_table_name}"
            staging_table_ids[table_name] = staging_table_id

            job_config = bigquery.LoadJobConfig(
                source_format=bigquery.SourceFormat.CSV,
                skip_leading_rows=1,
                schema=[bigquery.SchemaField(name, "STRING") for name in FIELD_NAMES[table_name]],
                autodetect=False,
                write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
                create_disposition=bigquery.CreateDisposition.CREATE_IF_NEEDED,
            )
            job = bigquery_client.load_table_from_uri(
                uris[table_name], staging_table_id, job_config=job_config, location=location
            )
            job.result()

            staging_rows = bigquery_client.get_table(staging_table_id).num_rows
            expected_rows = manifest["row_counts"][table_name]
            if staging_rows != expected_rows:
                raise RuntimeError(
                    f"Row-count mismatch for {table_name}: expected {expected_rows}, "
                    f"loaded {staging_rows}"
                )
            loaded_rows[table_name] = staging_rows

        # 3. All staging tables validated successfully -> Promote/copy to target tables
        for table_name in TABLES:
            target_table_id = f"{project_id}.{dataset_id}.{table_name}"
            staging_table_id = staging_table_ids[table_name]

            copy_config = bigquery.CopyJobConfig(
                write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
                create_disposition=bigquery.CreateDisposition.CREATE_IF_NEEDED,
            )
            copy_job = bigquery_client.copy_table(
                staging_table_id, target_table_id, job_config=copy_config, location=location
            )
            copy_job.result()

        duration = time.time() - start_time
        completed_at = datetime.now(timezone.utc)

        # 4. Record successful audit record
        _record_ingestion_run(
            bigquery_client,
            project_id,
            dataset_id,
            {
                "run_id": run_id,
                "status": "SUCCESS",
                "started_at": started_at.isoformat(),
                "completed_at": completed_at.isoformat(),
                "duration_seconds": round(duration, 2),
                "source_prefix": f"gs://{bucket_name}/{prefix}/",
                "row_counts_json": json.dumps(loaded_rows),
                "error_message": None,
            },
        )

    except Exception as exc:
        duration = time.time() - start_time
        completed_at = datetime.now(timezone.utc)
        _record_ingestion_run(
            bigquery_client,
            project_id,
            dataset_id,
            {
                "run_id": run_id,
                "status": "FAILED",
                "started_at": started_at.isoformat(),
                "completed_at": completed_at.isoformat(),
                "duration_seconds": round(duration, 2),
                "source_prefix": f"gs://{bucket_name}/{prefix}/",
                "row_counts_json": json.dumps(loaded_rows),
                "error_message": str(exc),
            },
        )
        raise
    finally:
        # Clean up temporary staging tables
        for stg_id in staging_table_ids.values():
            try:
                bigquery_client.delete_table(stg_id, not_found_ok=True)
            except Exception:
                pass

    return {
        "run_id": run_id,
        "source_prefix": f"gs://{bucket_name}/{prefix}/",
        "row_counts": loaded_rows,
        "duration_seconds": round(duration, 2),
        "manifest_anomalies": manifest.get("injected_data_quality_conditions", {}),
    }
