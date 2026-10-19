{{ config(materialized='table') }}

select *
from {{ ref('stg_clinical_events') }}
qualify row_number() over (
  partition by source_event_key, encounter_id, event_type
  order by ingested_at, event_id
) = 1
