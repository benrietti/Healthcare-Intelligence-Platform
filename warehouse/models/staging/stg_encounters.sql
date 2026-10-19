{{ config(materialized='view') }}

select
  cast(encounter_id as string) as encounter_id,
  cast(patient_id as string) as patient_id,
  cast(facility_id as string) as facility_id,
  safe_cast(admission_ts as timestamp) as admission_ts,
  safe_cast(discharge_ts as timestamp) as discharge_ts,
  cast(service_line as string) as service_line,
  cast(primary_diagnosis_group as string) as primary_diagnosis_group,
  cast(payer as string) as payer,
  cast(discharge_disposition as string) as discharge_disposition,
  safe_cast(length_of_stay_hours as float64) as length_of_stay_hours,
  safe_cast(readmitted_30d as bool) as readmitted_30d,
  safe_cast(synthetic as bool) as synthetic
from {{ source('synthetic_raw', 'encounters') }}
