"""Execute cloud warehouse + corrected ML + reporting in dependency order.

Uses existing ADC credentials. Deployment and billing are explicitly external
prerequisites. Publish/refresh is withheld after any failed command.
"""
import json
import os
import subprocess
import sys
from pathlib import Path
import pandas as pd
from google.cloud import bigquery
from healthcare_capstone.demo import fit_model, CLAIM_FEATURES
from healthcare_capstone.ml.features import load_encounter_frame,engineer_features,ADMISSION_FEATURES


def dbt(*args):
    subprocess.run(['dbt',*args,'--project-dir','warehouse','--profiles-dir','warehouse'],check=True)


def main():
    project=os.environ['GCP_PROJECT_ID'];analytics=os.environ.get('DBT_ANALYTICS_DATASET','healthcare_capstone_analytics');ml=os.environ.get('ML_PREDICTIONS_DATASET','healthcare_capstone_ml')
    client=bigquery.Client(project=project)
    dataset=bigquery.Dataset(f'{project}.{ml}');dataset.location=os.environ.get('GCP_LOCATION','US');client.create_dataset(dataset,exists_ok=True)
    # Build only the upstream encounter mart before prediction sources exist.
    dbt('build','--select','+dim_patient','+fct_encounter_operations')
    frame=engineer_features(load_encounter_frame(project,analytics))
    frame['discharge_ts']=pd.to_datetime(frame.discharge_ts,utc=True)
    frame['label_ready']=frame.discharge_ts+pd.Timedelta(days=30)
    out=Path('data/cloud');out.mkdir(parents=True,exist_ok=True)
    horizon=pd.Timestamp(os.environ.get('SOURCE_OBSERVATION_END','2025-12-31'),tz='UTC')
    models=[('readmission_30d',frame[frame.label_ready<=horizon],ADMISSION_FEATURES,'readmitted_30d','admission_ts','label_ready',True),
            ('length_of_stay',frame,ADMISSION_FEATURES,'length_of_stay_hours','admission_ts','discharge_ts',False)]
    claims=client.query(f'SELECT * FROM `{project}.{analytics}.stg_claims` WHERE adjudicated_at IS NOT NULL').to_dataframe()
    for col in ['claim_submit_ts','adjudicated_at']:claims[col]=pd.to_datetime(claims[col],utc=True)
    claims['billed_amount']=claims.billed_amount.astype(float)
    claims['denied']=claims.claim_status.eq('denied').astype(int)
    models.append(('claim_denial',claims,CLAIM_FEATURES,'denied','claim_submit_ts','adjudicated_at',True))
    drift=[]
    for name,data,features,target,predtime,labeltime,isclass in models:
        preds,_=fit_model(data,features,target,predtime,labeltime,name,out,isclass)
        if name=='readmission_30d':preds=preds.rename(columns={'prediction':'readmission_probability','actual':'readmitted_30d_actual'})
        elif name=='length_of_stay':preds=preds.rename(columns={'prediction':'length_of_stay_hours_predicted','actual':'length_of_stay_hours_actual'})
        else:preds=preds.rename(columns={'prediction':'denial_probability','actual':'denied_actual'})
        client.load_table_from_dataframe(preds,f'{project}.{ml}.ml_{name}_predictions',job_config=bigquery.LoadJobConfig(write_disposition='WRITE_TRUNCATE')).result()
        for row in json.loads((out/'models'/name/'drift.json').read_text()):
            drift.append(dict(model_name=name,**row,evaluated_at=pd.Timestamp.now(tz='UTC')))
    client.load_table_from_dataframe(pd.DataFrame(drift),f'{project}.{ml}.model_drift',job_config=bigquery.LoadJobConfig(write_disposition='WRITE_TRUNCATE')).result()
    from healthcare_capstone.operations import build_operations
    # Milestones are a clearly labeled synthetic design demo seeded separately.
    build_operations(frame,Path('warehouse/seeds'))
    beds=pd.read_csv('warehouse/seeds/bed_milestones.csv')
    beds=beds.drop(columns=['bed_ready_ts','turnover_minutes','readiness_status','ed_dwell_minutes'])
    beds.to_csv('warehouse/seeds/bed_milestones.csv',index=False)
    dbt('seed')
    dbt('build')
    dbt('source','freshness','--select','source:synthetic_raw')
    print('Cloud build and tests completed. Refresh Power BI separately and verify the visuals.')
if __name__=='__main__':main()
