"""Check compiled BigQuery SELECT statements without executing or modifying data."""
import json
import os
from pathlib import Path
from google.cloud import bigquery
client=bigquery.Client(project=os.environ['GCP_PROJECT_ID']);limit=int(os.environ.get('MAX_QUERY_BYTES',str(1024**3)));results=[]
paths=list(Path('warehouse/target/compiled/healthcare_capstone/models').rglob('*.sql'))
if not paths:raise SystemExit('No compiled models to validate')
for path in paths:
 job=client.query(path.read_text(),job_config=bigquery.QueryJobConfig(dry_run=True,use_query_cache=False))
 results.append(dict(model=str(path),bytes=job.total_bytes_processed,passed=job.total_bytes_processed<=limit))
out=Path('data/cloud');out.mkdir(parents=True,exist_ok=True);(out/'pr-query-checks.json').write_text(json.dumps(results,indent=2))
raise SystemExit(not all(x['passed'] for x in results))
