{{ config(materialized='view') }}
select model_name, feature, psi, threshold, status, reference_missing_rate,
 current_missing_rate, evaluated_at
from {{ source('ml', 'model_drift') }}
