{{ config(materialized='view') }}
select
 c.claim_id, c.encounter_id, c.payer, c.claim_submit_ts,
 c.billed_amount, c.authorization_present, c.documentation_complete,
 c.procedure_group, p.denial_probability,
 row_number() over(order by p.denial_probability desc, c.claim_id) as review_rank
from {{ ref('stg_claims') }} c
join {{ source('ml', 'ml_claim_denial_predictions') }} p using(claim_id)
