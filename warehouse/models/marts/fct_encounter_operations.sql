{{
  config(
    materialized='table',
    partition_by={"field": "admission_date", "data_type": "date", "granularity": "month"},
    cluster_by=["facility_id", "service_line"]
  )
}}

with event_summary as (
  select
    encounter_id,
    count(*) as event_count,
    countif(has_missing_event_ts) as events_missing_timestamp,
    countif(has_missing_department) as events_missing_department,
    countif(arrival_delay_minutes > 60 * 24) as events_arriving_over_24h_late,
    max(ingested_at) as last_event_ingested_at
  from {{ ref('int_clinical_events_deduplicated') }}
  group by encounter_id
), claims as (
  select
    encounter_id,
    sum(billed_amount) as billed_amount,
    sum(allowed_amount) as allowed_amount,
    sum(paid_amount) as paid_amount,
    countif(claim_status = 'denied') as denied_claim_count
  from {{ ref('stg_claims') }}
  group by encounter_id
)
select
  e.encounter_id,
  e.patient_id,
  e.facility_id,
  date(e.admission_ts) as admission_date,
  e.admission_ts,
  e.discharge_ts,
  e.service_line,
  e.primary_diagnosis_group,
  e.payer,
  e.discharge_disposition,
  e.length_of_stay_hours,
  e.readmitted_30d,
  e.synthetic,
  coalesce(v.event_count, 0) as event_count,
  coalesce(v.events_missing_timestamp, 0) as events_missing_timestamp,
  coalesce(v.events_missing_department, 0) as events_missing_department,
  coalesce(v.events_arriving_over_24h_late, 0) as events_arriving_over_24h_late,
  v.last_event_ingested_at,
  c.billed_amount,
  c.allowed_amount,
  c.paid_amount,
  coalesce(c.denied_claim_count, 0) as denied_claim_count
from {{ ref('stg_encounters') }} e
left join event_summary v using (encounter_id)
left join claims c using (encounter_id)
