{{ config(materialized='view') }}

select
  cast(event_id as string) as event_id,
  cast(source_event_key as string) as source_event_key,
  cast(encounter_id as string) as encounter_id,
  safe_cast(nullif(event_ts, '') as timestamp) as event_ts,
  safe_cast(ingested_at as timestamp) as ingested_at,
  cast(event_type as string) as event_type,
  nullif(cast(department as string), '') as department,
  cast(event_status as string) as event_status,
  cast(source_system as string) as source_system,
  cast(source_code as string) as source_code,
  safe_cast(synthetic as bool) as synthetic,
  event_ts is null or event_ts = '' as has_missing_event_ts,
  department is null or department = '' as has_missing_department,
  timestamp_diff(
    safe_cast(ingested_at as timestamp),
    safe_cast(nullif(event_ts, '') as timestamp),
    minute
  ) as arrival_delay_minutes
from {{ source('synthetic_raw', 'clinical_events') }}
