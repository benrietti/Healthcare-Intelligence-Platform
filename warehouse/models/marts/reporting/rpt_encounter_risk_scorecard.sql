{{
  config(
    materialized = 'view'
  )
}}

-- One row per encounter with operational facts, patient dimensions,
-- and ML scores joined in. Powers encounter-level dashboards and
-- lets BI users filter by predicted risk alongside real outcomes.
-- Readmission and LOS scores only exist for encounters in the
-- held-out test fold, so the left joins are expected to be sparse.

with encounters as (
    select * from {{ ref('fct_encounter_operations') }}
),

patients as (
    select * from {{ ref('dim_patient') }}
),

readmission_scores as (
    select
        encounter_id,
        readmission_probability,
        model_name as readmission_model_name,
        cast(scored_at as timestamp) as readmission_scored_at
    from {{ source('ml', 'ml_readmission_predictions') }}
),

los_scores as (
    select
        encounter_id,
        length_of_stay_hours_predicted,
        model_name as length_of_stay_model_name,
        cast(scored_at as timestamp) as length_of_stay_scored_at
    from {{ source('ml', 'ml_length_of_stay_predictions') }}
)

select
    e.encounter_id,
    e.patient_id,
    e.facility_id,
    e.admission_ts,
    e.admission_date,
    e.discharge_ts,
    e.service_line,
    e.primary_diagnosis_group,
    e.payer,
    e.discharge_disposition,

    -- Patient context
    p.sex,
    p.home_state,
    p.birth_year,
    extract(year from e.admission_ts) - p.birth_year as patient_age_at_admission,

    -- Operational facts
    e.length_of_stay_hours,
    e.event_count,
    e.events_missing_timestamp,
    e.events_missing_department,
    e.events_arriving_over_24h_late,

    -- Financials
    e.billed_amount,
    e.allowed_amount,
    e.paid_amount,
    e.denied_claim_count,

    -- Outcomes
    e.readmitted_30d,

    -- ML scores (null for encounters outside the test fold)
    r.readmission_probability,
    r.readmission_model_name,
    r.readmission_scored_at,
    l.length_of_stay_hours_predicted,
    l.length_of_stay_model_name,
    l.length_of_stay_scored_at,

    -- Derived error metric when both actual and predicted LOS are present
    case
        when l.length_of_stay_hours_predicted is not null
             and e.length_of_stay_hours is not null
        then l.length_of_stay_hours_predicted - e.length_of_stay_hours
    end as length_of_stay_prediction_error_hours

from encounters e
left join patients p on e.patient_id = p.patient_id
left join readmission_scores r on e.encounter_id = r.encounter_id
left join los_scores l on e.encounter_id = l.encounter_id
