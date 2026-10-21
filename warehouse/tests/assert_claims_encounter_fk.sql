-- Referential integrity: every claim must map to an existing encounter
select
    c.claim_id,
    c.encounter_id
from {{ ref('stg_claims') }} c
left join {{ ref('stg_encounters') }} e using (encounter_id)
where e.encounter_id is null
