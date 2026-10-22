"""Dry-run reporting queries and reject estimates above the configured budget."""
import json
import os
from pathlib import Path
from google.cloud import bigquery
project=os.environ['GCP_PROJECT_ID'];dataset=os.environ.get('DBT_ANALYTICS_DATASET','healthcare_capstone_analytics');client=bigquery.Client(project=project)
limit=int(os.environ.get('MAX_QUERY_BYTES',str(1024**3)));results=[]
for table in ['rpt_encounter_risk_scorecard','rpt_data_quality_overview','rpt_claim_denial_queue','rpt_model_drift']:
 job=client.query(f'SELECT * FROM `{project}.{dataset}.{table}`',job_config=bigquery.QueryJobConfig(dry_run=True,use_query_cache=False))
 results.append(dict(table=table,estimated_bytes=job.total_bytes_processed,max_bytes=limit,passed=job.total_bytes_processed<=limit))
p=Path('data/cloud/query_budget.json');p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(results,indent=2))
raise SystemExit(not all(x['passed'] for x in results))
