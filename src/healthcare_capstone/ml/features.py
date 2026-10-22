"""Feature engineering utilities for Phase 2 ML models.

Pulls encounter-level data from the BigQuery analytics marts, derives
leakage-safe features, and provides a chronological split helper so that
training only ever learns from encounters that happened before the test
window.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Tuple

import pandas as pd


FEATURE_QUERY = """
select
  f.encounter_id,
  f.patient_id,
  f.facility_id,
  f.admission_ts,
  f.discharge_ts,
  f.admission_date,
  f.service_line,
  f.primary_diagnosis_group,
  f.payer,
  f.discharge_disposition,
  f.length_of_stay_hours,
  f.readmitted_30d,
  f.event_count,
  f.events_missing_timestamp,
  f.events_missing_department,
  f.events_arriving_over_24h_late,
  f.billed_amount,
  f.allowed_amount,
  f.paid_amount,
  f.denied_claim_count,
  p.birth_year,
  p.sex,
  p.home_state
from `{project}.{dataset}.fct_encounter_operations` f
left join `{project}.{dataset}.dim_patient` p using (patient_id)
where f.admission_ts is not null
"""


@dataclass
class SplitFrames:
    """Container for chronologically ordered train/test frames."""

    X_train: pd.DataFrame
    X_test: pd.DataFrame
    y_train: pd.Series
    y_test: pd.Series
    cutoff: pd.Timestamp


def load_encounter_frame(
    project: str | None = None,
    dataset: str | None = None,
) -> pd.DataFrame:
    """Query encounter + patient marts into a pandas DataFrame."""
    project = project or os.environ["GCP_PROJECT_ID"]
    dataset = dataset or os.environ.get(
        "DBT_ANALYTICS_DATASET", "healthcare_capstone_analytics"
    )
    from google.cloud import bigquery
    client = bigquery.Client(project=project)
    query = FEATURE_QUERY.format(project=project, dataset=dataset)
    df = client.query(query).to_dataframe()
    df["admission_ts"] = pd.to_datetime(df["admission_ts"], utc=True)
    return df


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Derive leakage-safe features from the raw encounter frame."""
    out = df.copy()
    admission_year = out["admission_ts"].dt.year
    out["patient_age_at_admission"] = admission_year - out["birth_year"]
    out["admission_hour"] = out["admission_ts"].dt.hour
    out["admission_dow"] = out["admission_ts"].dt.dayofweek
    out["admission_month"] = out["admission_ts"].dt.month

    numeric_fills = {
        "event_count": 0,
        "events_missing_timestamp": 0,
        "events_missing_department": 0,
        "events_arriving_over_24h_late": 0,
        "billed_amount": 0.0,
        "allowed_amount": 0.0,
        "paid_amount": 0.0,
        "denied_claim_count": 0,
    }
    out = out.fillna(numeric_fills)

    out["paid_ratio"] = (
        out["paid_amount"] / out["billed_amount"].replace(0, pd.NA)
    ).astype(float).fillna(0.0)

    categorical_cols = [
        "facility_id",
        "service_line",
        "primary_diagnosis_group",
        "payer",
        "discharge_disposition",
        "sex",
        "home_state",
    ]
    for col in categorical_cols:
        out[col] = out[col].fillna("unknown").astype("category")

    return out


def chronological_split(
    df: pd.DataFrame,
    target_col: str,
    test_fraction: float = 0.2,
    drop_cols: tuple[str, ...] = (
        "encounter_id",
        "patient_id",
        "admission_ts",
        "discharge_ts",
        "admission_date",
        "birth_year",
    ),
) -> SplitFrames:
    """Order by admission_ts and hold out the latest fraction for testing."""
    ordered = df.sort_values("admission_ts", kind="stable")
    cutoff_idx = int(len(ordered) * (1 - test_fraction))
    cutoff_ts = ordered.iloc[cutoff_idx]["admission_ts"]

    train_df = ordered.iloc[:cutoff_idx]
    test_df = ordered.iloc[cutoff_idx:]

    # Explicit admission-time allowlist: outcome and encounter-total columns
    # must never become features just because a warehouse adds a new column.
    feature_cols = [c for c in ADMISSION_FEATURES if c in ordered.columns]
    if not feature_cols:
        raise ValueError("No admission-time features available")
    return SplitFrames(
        X_train=train_df[feature_cols],
        X_test=test_df[feature_cols],
        y_train=train_df[target_col],
        y_test=test_df[target_col],
        cutoff=cutoff_ts,
    )


ADMISSION_FEATURES = (
    "facility_id", "service_line", "primary_diagnosis_group", "payer",
    "sex", "home_state", "patient_age_at_admission", "admission_hour",
    "admission_dow", "admission_month",
)


def available_events(events, cutoff):
    """Both event and recorded time must precede a per-encounter cutoff.

    cutoff is a frame with encounter_id and prediction_ts. Missing or future
    timestamps are excluded; late documentation cannot leak into a snapshot.
    """
    joined = events.merge(cutoff, on="encounter_id", validate="many_to_one")
    for col in ("event_ts", "ingested_at", "prediction_ts"):
        joined[col] = pd.to_datetime(joined[col], utc=True, errors="coerce", format="ISO8601")
    return joined[(joined.event_ts <= joined.prediction_ts) &
                  (joined.ingested_at <= joined.prediction_ts)].copy()
