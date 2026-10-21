{{
  config(
    materialized = 'view'
  )
}}

-- Pipeline-health view surfaced to BI. One row per admission_date with
-- counts of encounters, clinical events, and the quality flags that
-- fct_encounter_operations already tracks. Keeps the "is the pipeline
-- healthy?" question answerable with a single tile, independent of the
-- clinical or financial dashboards.

with encounters as (
    select
        admission_date,
        count(*) as encounter_count,
        sum(event_count) as clinical_event_count,
        sum(events_missing_timestamp) as events_missing_timestamp,
        sum(events_missing_department) as events_missing_department,
        sum(events_arriving_over_24h_late) as events_arriving_over_24h_late,
        sum(denied_claim_count) as denied_claim_count
    from {{ ref('fct_encounter_operations') }}
    group by admission_date
),

ingest_runs as (
    select
        date(started_at) as run_date,
        count(*) as ingest_run_count,
        countif(status = 'success') as ingest_run_success_count,
        countif(status != 'success') as ingest_run_failure_count,
        max(started_at) as last_ingest_run_at
    from {{ source('synthetic_raw', '_ingestion_runs') }}
    group by run_date
)

select
    coalesce(e.admission_date, i.run_date) as reporting_date,

    -- Volume
    e.encounter_count,
    e.clinical_event_count,

    -- Quality flags from the fact
    e.events_missing_timestamp,
    e.events_missing_department,
    e.events_arriving_over_24h_late,
    e.denied_claim_count,

    -- Flag rates (null-safe)
    safe_divide(e.events_missing_timestamp, e.clinical_event_count) as events_missing_timestamp_rate,
    safe_divide(e.events_missing_department, e.clinical_event_count) as events_missing_department_rate,
    safe_divide(e.events_arriving_over_24h_late, e.clinical_event_count) as events_arriving_over_24h_late_rate,

    -- Ingestion-run audit
    i.ingest_run_count,
    i.ingest_run_success_count,
    i.ingest_run_failure_count,
    i.last_ingest_run_at

from encounters e
full outer join ingest_runs i on e.admission_date = i.run_date
order by reporting_date desc
