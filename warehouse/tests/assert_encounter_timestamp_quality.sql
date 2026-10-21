-- Timestamp quality: discharge must occur after admission, and admission_date must match admission_ts
select
    encounter_id,
    admission_ts,
    discharge_ts,
    admission_date
from {{ ref('fct_encounter_operations') }}
where
    discharge_ts < admission_ts
    or admission_date != date(admission_ts)
