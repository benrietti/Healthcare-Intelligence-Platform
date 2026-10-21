{{ config(materialized='table') }}

select
  patient_id,
  birth_year,
  sex,
  home_state,
  synthetic
from {{ ref('stg_patients') }}
