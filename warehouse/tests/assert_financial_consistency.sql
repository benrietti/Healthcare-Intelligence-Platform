-- Financial consistency: amounts must be non-negative and paid <= allowed <= billed
select
    encounter_id,
    billed_amount,
    allowed_amount,
    paid_amount
from {{ ref('fct_encounter_operations') }}
where
    coalesce(billed_amount, 0) < 0
    or coalesce(allowed_amount, 0) < 0
    or coalesce(paid_amount, 0) < 0
    or allowed_amount > billed_amount
    or paid_amount > allowed_amount
