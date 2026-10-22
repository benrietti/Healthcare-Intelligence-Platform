{{ config(materialized='view') }}
-- Explicitly synthetic milestones; max() alone would silently skip null milestones.
select *,
 case when administrative_discharge_ts is not null
       and transport_departure_ts is not null and cleaning_complete_ts is not null
 then greatest(administrative_discharge_ts, transport_departure_ts, cleaning_complete_ts)
 end as bed_ready_ts,
 timestamp_diff(ed_departure_ts,ed_arrival_ts,minute) as ed_dwell_minutes
from {{ ref('bed_milestones') }}
