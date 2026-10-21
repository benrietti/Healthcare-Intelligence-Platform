# Initial engineering decisions

## Synthetic data only

The generator uses deterministic seeds and a manifest of injected quality cases. This makes demos reproducible and lets reviewers distinguish designed anomalies from accidental failures. No real patient, employer, or proprietary data belongs in this repository.

## Preserve raw event evidence

The raw event file preserves `event_ts` (when an event happened), `ingested_at` (when it arrived), and `source_event_key` (upstream identity). Downstream models can then measure late arrival, missing timestamps, replayed messages, and event ordering explicitly.

## Separate event time from arrival time

Operational sequence and clinical duration use valid event time; pipeline-latency reporting uses arrival time. This avoids treating a late-arriving message as if the care event itself happened late.

## Keep prediction labels honest

The first readmission label is a synthetic outcome derived from subsequent generated encounters. The project will use chronological splitting and document the limits of that label. A model score is an engineering and methods demonstration, not a care recommendation.

## Optimize after defining access patterns

BigQuery partitions and clustering will be applied to date-grained fact tables after the model grain and common filter paths are established. Cost choices will be recorded with query examples instead of adding partitions to every table by default.

## ML phase: honest reporting over flattering metrics

Phase 2 adds two scoring models that read from the analytics marts, split chronologically, and write predictions back to a dedicated `*_ml` dataset so downstream BI can join them to the operational facts.

- **30-day readmission classifier** (HistGradientBoostingClassifier): test ROC-AUC ~0.75 with PR-AUC ~0.19 against a 6% positive rate. Train metrics saturate because the training frame is small; the chronological holdout is the number worth citing.
- **Length of stay regressor** (HistGradientBoostingRegressor): test MAE ~13 hours and a negative R^2. Train metrics look strong (R^2 ~0.88) but do not survive the time cutoff. This is recorded, not hidden: the chronological split surfaced a real weakness that a random split would have masked.

The split helper always orders by `admission_ts` and reserves the latest fraction for test. Features derived from the admission time (hour, day of week, patient age) are allowed; anything that would only be known after discharge is excluded or is the target itself. Model artifacts and metrics JSON are versioned under `data/models/<model_name>/`.
