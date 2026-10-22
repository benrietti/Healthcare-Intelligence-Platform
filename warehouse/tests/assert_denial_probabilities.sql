select * from {{ source('ml', 'ml_claim_denial_predictions') }}
where denial_probability is null or denial_probability < 0 or denial_probability > 1
