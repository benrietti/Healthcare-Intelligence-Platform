"""Persist machine-readable freshness, quality, drift, and job-failure alerts."""
import json
import os
from pathlib import Path
from datetime import datetime,timezone
from google.cloud import bigquery


def main():
    project=os.environ['GCP_PROJECT_ID'];dataset=os.environ.get('DBT_ANALYTICS_DATASET','healthcare_capstone_analytics');ml=os.environ.get('ML_PREDICTIONS_DATASET','healthcare_capstone_ml')
    policy=json.loads(Path('monitoring/policy.json').read_text());client=bigquery.Client(project=project)
    row=next(iter(client.query(f'''select max(last_ingest_run_at) as last_run,
     sum(ingest_run_failure_count) as failures,
     safe_divide(sum(events_missing_timestamp),sum(clinical_event_count)) as missing_timestamp_rate,
     safe_divide(sum(events_missing_department),sum(clinical_event_count)) as missing_department_rate,
     safe_divide(sum(events_arriving_over_24h_late),sum(clinical_event_count)) as late_arrival_rate
     from `{project}.{dataset}.rpt_data_quality_overview`''').result()))
    alerts=[];now=datetime.now(timezone.utc)
    if row.last_run is None or (now-row.last_run).total_seconds()>policy['freshness_hours']*3600:alerts.append('ingestion freshness threshold exceeded')
    if row.failures:alerts.append('failed ingestion runs recorded')
    for key in ['missing_timestamp_rate','missing_department_rate','late_arrival_rate']:
        value=getattr(row,key)
        if value is None or value>policy['max_'+key]:alerts.append(key+' unknown or exceeds threshold')
    drift=list(client.query(f"SELECT model_name, feature, psi FROM `{project}.{ml}.model_drift` WHERE status != 'ok'").result())
    alerts.extend(f'drift: {x.model_name}.{x.feature} PSI={x.psi}' for x in drift)
    out=Path('data/cloud');out.mkdir(parents=True,exist_ok=True)
    report=dict(evaluated_at=now.isoformat(),owner=policy['owner'],response=policy['response'],alerts=alerts)
    (out/'alerts.json').write_text(json.dumps(report,indent=2))
    # Persist alerts for BI/operations; no email or external messages are sent.
    rows=[dict(evaluated_at=now,owner=policy['owner'],severity='warning',message=x) for x in alerts]
    import pandas as pd
    frame=pd.DataFrame(rows,columns=['evaluated_at','owner','severity','message'])
    schema=[bigquery.SchemaField('evaluated_at','TIMESTAMP'),bigquery.SchemaField('owner','STRING'),bigquery.SchemaField('severity','STRING'),bigquery.SchemaField('message','STRING')]
    client.load_table_from_dataframe(frame,f'{project}.{ml}.platform_alerts',job_config=bigquery.LoadJobConfig(schema=schema,write_disposition='WRITE_TRUNCATE')).result()
    print(json.dumps(report))
    raise SystemExit(bool(alerts))
if __name__=='__main__':main()
