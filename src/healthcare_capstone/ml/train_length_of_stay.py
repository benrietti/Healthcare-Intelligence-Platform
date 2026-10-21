"""Train and evaluate a length-of-stay regressor.

Uses the same engineered feature set and chronological split helper as
the readmission classifier, but predicts length_of_stay_hours. Metrics
and predictions are persisted the same way for downstream BI
consumption.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from healthcare_capstone.ml.features import (
    chronological_split,
    engineer_features,
    load_encounter_frame,
)


MODEL_NAME = "length_of_stay"
TARGET_COL = "length_of_stay_hours"


def build_pipeline(categorical_cols: list[str], numeric_cols: list[str]) -> Pipeline:
    preprocessor = ColumnTransformer(
        transformers=[
            (
                "cat",
                OneHotEncoder(handle_unknown="ignore", min_frequency=10),
                categorical_cols,
            ),
            ("num", "passthrough", numeric_cols),
        ]
    )
    model = HistGradientBoostingRegressor(
        max_depth=6,
        learning_rate=0.05,
        max_iter=400,
        l2_regularization=1.0,
        random_state=42,
    )
    return Pipeline(steps=[("preprocess", preprocessor), ("model", model)])


def evaluate(y_true: pd.Series, y_pred: np.ndarray) -> dict:
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    return {
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "rmse": rmse,
        "r2": float(r2_score(y_true, y_pred)),
        "mean_actual": float(np.mean(y_true)),
        "mean_predicted": float(np.mean(y_pred)),
        "n_samples": int(len(y_true)),
    }


def write_predictions_to_bigquery(
    predictions: pd.DataFrame,
    project: str,
    dataset: str,
    table: str = "ml_length_of_stay_predictions",
) -> str:
    from google.cloud import bigquery

    client = bigquery.Client(project=project)
    table_id = f"{project}.{dataset}.{table}"
    job = client.load_table_from_dataframe(
        predictions,
        table_id,
        job_config=bigquery.LoadJobConfig(
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE
        ),
    )
    job.result()
    return table_id


def main() -> None:
    project = os.environ["GCP_PROJECT_ID"]
    dataset = os.environ.get("DBT_ANALYTICS_DATASET", "healthcare_capstone_analytics")
    output_dir = Path("data/models") / MODEL_NAME
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"[{MODEL_NAME}] Loading encounter frame from {project}.{dataset} ...")
    raw = load_encounter_frame(project=project, dataset=dataset)
    print(f"[{MODEL_NAME}] Loaded {len(raw):,} encounter rows")

    engineered = engineer_features(raw)
    engineered = engineered.dropna(subset=[TARGET_COL])
    engineered = engineered[engineered[TARGET_COL] > 0]

    split = chronological_split(engineered, target_col=TARGET_COL, test_fraction=0.2)
    print(
        f"[{MODEL_NAME}] Train: {len(split.X_train):,} | "
        f"Test: {len(split.X_test):,} | Cutoff: {split.cutoff}"
    )

    categorical_cols = [
        c for c in split.X_train.columns if str(split.X_train[c].dtype) == "category"
    ]
    numeric_cols = [c for c in split.X_train.columns if c not in categorical_cols]

    pipeline = build_pipeline(categorical_cols, numeric_cols)
    pipeline.fit(split.X_train, split.y_train)

    train_pred = pipeline.predict(split.X_train)
    test_pred = pipeline.predict(split.X_test)

    metrics = {
        "model": MODEL_NAME,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "cutoff_ts": split.cutoff.isoformat(),
        "train": evaluate(split.y_train, train_pred),
        "test": evaluate(split.y_test, test_pred),
    }
    print(json.dumps(metrics, indent=2))

    joblib.dump(pipeline, output_dir / "model.joblib")
    (output_dir / "metrics.json").write_text(json.dumps(metrics, indent=2))

    test_index = split.X_test.index
    predictions = pd.DataFrame(
        {
            "encounter_id": engineered.loc[test_index, "encounter_id"].values,
            "patient_id": engineered.loc[test_index, "patient_id"].values,
            "admission_ts": engineered.loc[test_index, "admission_ts"].values,
            "length_of_stay_hours_actual": split.y_test.values,
            "length_of_stay_hours_predicted": test_pred,
            "model_name": MODEL_NAME,
            "scored_at": datetime.now(timezone.utc),
        }
    )

    ml_dataset = os.environ.get("ML_PREDICTIONS_DATASET", dataset)
    table_id = write_predictions_to_bigquery(predictions, project, ml_dataset)
    print(f"[{MODEL_NAME}] Wrote {len(predictions):,} predictions to {table_id}")


if __name__ == "__main__":
    main()
