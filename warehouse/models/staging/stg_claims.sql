{{ config(materialized='view') }}

select
  cast(claim_id as string) as claim_id,
  cast(encounter_id as string) as encounter_id,
  cast(payer as string) as payer,
  safe_cast(claim_submit_ts as timestamp) as claim_submit_ts,
  safe_cast(billed_amount as numeric) as billed_amount,
  safe_cast(allowed_amount as numeric) as allowed_amount,
  safe_cast(paid_amount as numeric) as paid_amount,
  cast(claim_status as string) as claim_status,
  nullif(cast(denial_reason as string), '') as denial_reason,
  safe_cast(synthetic as bool) as synthetic
from {{ source('synthetic_raw', 'claims') }}
