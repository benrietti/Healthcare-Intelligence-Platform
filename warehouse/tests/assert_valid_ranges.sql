-- Valid ranges: length of stay and all event/anomaly counts must be >= 0
select
    encounter_id,
    length_of_stay_hours,
    event_count,
    events_missing_timestamp,
    events_missing_department,
    events_arriving_over_24h_late
from {{ ref('fct_encounter_operations') }}
where
    length_of_stay_hours < 0
    or event_count < 0
    or events_missing_timestamp < 0
    or events_missing_department < 0
    or events_arriving_over_24h_late < 0
