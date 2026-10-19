# Synthetic source data contract

All four tables are loaded to BigQuery as strings in the raw layer. Typed parsing and quality rules belong in dbt staging so raw input remains inspectable.

| File/table | Grain | Key | Purpose |
|---|---|---|---|
| `patients` | One synthetic patient | `patient_id` | Minimal patient attributes for cohort and demographic examples |
| `encounters` | One synthetic inpatient encounter | `encounter_id` | Facility, service line, dates, disposition, LOS, and derived 30-day readmission outcome |
| `clinical_events` | One source event or replay | `event_id` | Clinical/operational event time, arrival time, source key, type, and department |
| `claims` | One synthetic claim per encounter | `claim_id` | Billed, allowed, paid, payer, status, and denial reason |

## Field behavior

- Every row contains `synthetic=true`.
- `event_ts` is the event time; `ingested_at` is the platform arrival time.
- Blank event timestamps and departments, late arrivals, out-of-order rows, and repeated source keys are intentional in `clinical_events.csv`.
- Replayed event messages have a new `event_id` but can repeat `source_event_key`, encounter, and event type. Deduplication is a modeled decision, not a raw-layer deletion.
- `readmitted_30d` is derived from a subsequent generated encounter within 30 days after discharge. It is a synthetic demonstration outcome, not a clinical quality measure.
- Claim amounts are synthetic; they do not represent reimbursement rates or any real payer contract.

## Data-quality checks

Expected primary keys are unique and non-null. Encounter-to-patient and claim-to-encounter relationships must resolve. Event timestamps and departments may be null by design; curated output must retain counts of those conditions. Arrival lag uses `ingested_at - event_ts` and is undefined when the event timestamp is missing.
