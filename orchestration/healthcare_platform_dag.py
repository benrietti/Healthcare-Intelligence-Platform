"""Airflow 2.x DAG; install package/dbt/cloud dependencies on the worker.

No deployment occurs on import. AIRFLOW_PLATFORM_ROOT identifies the checked-out
repository; GOOGLE_APPLICATION_CREDENTIALS/ADC supplies worker credentials.
"""
import os
from datetime import datetime,timedelta,timezone
from airflow import DAG
from airflow.operators.bash import BashOperator
ROOT=os.environ.get('AIRFLOW_PLATFORM_ROOT','/opt/airflow/healthcare-platform')
with DAG('synthetic_healthcare_platform',start_date=datetime(2026,1,1,tzinfo=timezone.utc),schedule='@daily',catchup=False,default_args={'owner':'analytics-platform-owner','retries':1,'retry_delay':timedelta(minutes=5)},tags=['synthetic','portfolio']) as dag:
    build=BashOperator(task_id='generate_and_validate',cwd=ROOT,bash_command='python -m healthcare_capstone.demo --output data/demo --patients 2000 && python scripts/quality_gate.py --input data/demo')
    cloud=BashOperator(task_id='cloud_warehouse_models_tests',cwd=ROOT,bash_command='python -m healthcare_capstone.cli ingest-gcp --input data/demo/source --project-id "$GCP_PROJECT_ID" --bucket "$GCP_BUCKET" && PYTHONPATH=src python scripts/cloud_build.py')
    monitor=BashOperator(task_id="monitor_freshness_quality_drift",cwd=ROOT,bash_command="python scripts/cloud_monitor.py")
    build >> cloud >> monitor
