{{ config(materialized='view') }}
-- Synthetic flowsheet identifiers demonstrate a source-to-analytics crosswalk.
select e.event_id, e.encounter_id, e.event_ts, e.source_system, e.source_code,
 coalesce(c.analytical_category, 'unmapped') as analytical_category,
 e.synthetic
from {{ ref('int_clinical_events_deduplicated') }} e
left join {{ ref('clinical_taxonomy_crosswalk') }} c
 on e.source_system = c.source_system and e.source_code = c.source_code
