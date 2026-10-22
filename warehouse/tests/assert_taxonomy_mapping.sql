select * from {{ ref('rpt_clinical_taxonomy') }}
where analytical_category = 'unmapped' or not synthetic
