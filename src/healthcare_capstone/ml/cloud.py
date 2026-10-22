"""Shared cloud model training; local and cloud paths use identical controls."""
import os
from pathlib import Path
import pandas as pd
from google.cloud import bigquery
from healthcare_capstone.demo import fit_model,CLAIM_FEATURES
from healthcare_capstone.ml.features import engineer_features,load_encounter_frame,ADMISSION_FEATURES


def train_cloud_model(name):
    project=os.environ['GCP_PROJECT_ID'];analytics=os.environ.get('DBT_ANALYTICS_DATASET','healthcare_capstone_analytics');ml=os.environ.get('ML_PREDICTIONS_DATASET','healthcare_capstone_ml')
    client=bigquery.Client(project=project)
    if name=='claim_denial':
        frame=client.query(f'SELECT * FROM `{project}.{analytics}.stg_claims` WHERE adjudicated_at IS NOT NULL').to_dataframe()
        for col in ['claim_submit_ts','adjudicated_at']:frame[col]=pd.to_datetime(frame[col],utc=True)
        frame['billed_amount']=frame.billed_amount.astype(float)
        frame['denied']=frame.claim_status.eq('denied').astype(int)
        args=(frame,CLAIM_FEATURES,'denied','claim_submit_ts','adjudicated_at',True)
        names={'prediction':'denial_probability','actual':'denied_actual'}
    else:
        frame=engineer_features(load_encounter_frame(project,analytics));frame['discharge_ts']=pd.to_datetime(frame.discharge_ts,utc=True)
        if name=='readmission_30d':
            frame['label_ready']=frame.discharge_ts+pd.Timedelta(days=30)
            frame=frame[frame.label_ready<=pd.Timestamp(os.environ.get('SOURCE_OBSERVATION_END','2025-12-31'),tz='UTC')]
            args=(frame,ADMISSION_FEATURES,'readmitted_30d','admission_ts','label_ready',True)
            names={'prediction':'readmission_probability','actual':'readmitted_30d_actual'}
        elif name=='length_of_stay':
            args=(frame,ADMISSION_FEATURES,'length_of_stay_hours','admission_ts','discharge_ts',False)
            names={'prediction':'length_of_stay_hours_predicted','actual':'length_of_stay_hours_actual'}
        else:raise ValueError(name)
    frame,features,target,predtime,labeltime,classification=args
    preds,metrics=fit_model(frame,features,target,predtime,labeltime,name,Path('data/models').parent,classification)
    dataset=bigquery.Dataset(f'{project}.{ml}');dataset.location='US';client.create_dataset(dataset,exists_ok=True)
    client.load_table_from_dataframe(preds.rename(columns=names),f'{project}.{ml}.ml_{name}_predictions',job_config=bigquery.LoadJobConfig(write_disposition='WRITE_TRUNCATE')).result()
    return metrics
