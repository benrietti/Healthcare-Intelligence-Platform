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
