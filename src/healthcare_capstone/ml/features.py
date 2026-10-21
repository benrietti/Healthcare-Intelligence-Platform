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
from google.cloud import bigquery


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
    ordered = df.sort_values("admission_ts").reset_index(drop=True)
    cutoff_idx = int(len(ordered) * (1 - test_fraction))
    cutoff_ts = ordered.loc[cutoff_idx, "admission_ts"]

    train_df = ordered.iloc[:cutoff_idx]
    test_df = ordered.iloc[cutoff_idx:]

    feature_cols = [
        c for c in ordered.columns if c not in drop_cols and c != target_col
    ]
    return SplitFrames(
        X_train=train_df[feature_cols],
        X_test=test_df[feature_cols],
        y_train=train_df[target_col],
        y_test=test_df[target_col],
        cutoff=cutoff_ts,
    )
