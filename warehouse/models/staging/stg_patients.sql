{{ config(materialized='view') }}

select
  cast(patient_id as string) as patient_id,
  safe_cast(birth_year as int64) as birth_year,
  nullif(cast(sex as string), '') as sex,
  nullif(cast(home_state as string), '') as home_state,
  safe_cast(synthetic as bool) as synthetic
from {{ source('synthetic_raw', 'patients') }}
