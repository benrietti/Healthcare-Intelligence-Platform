{{
  config(
    materialized = 'view'
  )
}}

-- Daily rollup per facility and service line. Each row is one
-- (admission_date, facility_id, service_line) grouping and summarizes
-- throughput, length of stay (actual and predicted), readmission risk,
-- and pipeline data-quality flags. ML averages only reflect encounters
-- that fell in the held-out test fold, so counts are reported alongside.

with scorecard as (
    select * from {{ ref('rpt_encounter_risk_scorecard') }}
)

select
    admission_date,
    facility_id,
    service_line,

    -- Throughput
    count(*) as encounter_count,
    count(distinct patient_id) as distinct_patient_count,
    sum(case when readmitted_30d then 1 else 0 end) as readmitted_30d_count,
    safe_divide(
        sum(case when readmitted_30d then 1 else 0 end),
        count(*)
    ) as readmitted_30d_rate,

    -- Length of stay (actual)
    avg(length_of_stay_hours) as length_of_stay_hours_avg,
    approx_quantiles(length_of_stay_hours, 100)[offset(50)] as length_of_stay_hours_median,
    approx_quantiles(length_of_stay_hours, 100)[offset(90)] as length_of_stay_hours_p90,

    -- ML coverage and averages (null-safe)
    countif(readmission_probability is not null) as scored_readmission_encounter_count,
    avg(readmission_probability) as readmission_probability_avg,
    countif(length_of_stay_hours_predicted is not null) as scored_length_of_stay_encounter_count,
    avg(length_of_stay_hours_predicted) as length_of_stay_hours_predicted_avg,
    avg(abs(length_of_stay_prediction_error_hours)) as length_of_stay_mae_hours,

    -- Financials
    sum(billed_amount) as billed_amount_total,
    sum(paid_amount) as paid_amount_total,
    sum(denied_claim_count) as denied_claim_count_total,

    -- Pipeline data-quality flags
    sum(events_missing_timestamp) as events_missing_timestamp_total,
    sum(events_missing_department) as events_missing_department_total,
    sum(events_arriving_over_24h_late) as events_arriving_over_24h_late_total

from scorecard
group by 1, 2, 3
