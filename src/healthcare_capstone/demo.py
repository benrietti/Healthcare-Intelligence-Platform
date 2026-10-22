"""Reproducible local build and evidence for the synthetic portfolio platform.

Runs without cloud credentials. Cloud SQL and Power BI require their own
execution/refresh validation; local evidence never implies cloud deployment.
"""
from __future__ import annotations
import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.dummy import DummyClassifier, DummyRegressor
from sklearn.metrics import roc_auc_score, average_precision_score, brier_score_loss, mean_absolute_error, mean_squared_error, r2_score
from healthcare_capstone.generator import generate_dataset
from healthcare_capstone.ml.features import ADMISSION_FEATURES
from healthcare_capstone.ml.monitoring import drift_report, explain, local_explanations

CLAIM_FEATURES = ('payer','billed_amount','authorization_present','documentation_complete','procedure_group')


def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str, allow_nan=False))


def model_pipeline(X, classification):
    categorical = [c for c in X if not pd.api.types.is_numeric_dtype(X[c])]
    numeric = [c for c in X if c not in categorical]
    pre = ColumnTransformer([
        ('cat', Pipeline([('fill', SimpleImputer(strategy='most_frequent')),
                          ('encode',OneHotEncoder(handle_unknown='ignore',sparse_output=False))]), categorical),
        ('num', SimpleImputer(strategy='median'), numeric)])
    cls = HistGradientBoostingClassifier if classification else HistGradientBoostingRegressor
    return Pipeline([('preprocess',pre),('model',cls(max_iter=100,max_depth=3,l2_regularization=2,random_state=42))])


def metrics(y, predicted, classification):
    if classification:
        return dict(roc_auc=float(roc_auc_score(y,predicted)) if len(set(y))==2 else None,
                    average_precision=float(average_precision_score(y,predicted)),
                    brier_score=float(brier_score_loss(y,predicted)),positive_rate=float(y.mean()),n_samples=len(y))
    return dict(mae=float(mean_absolute_error(y,predicted)),rmse=float(np.sqrt(mean_squared_error(y,predicted))),
                r2=float(r2_score(y,predicted)),n_samples=len(y))


def fit_model(frame, features, target, time_col, label_available_col, name, out, classification=True):
    # The date at which the label matures must precede the first evaluation
    # prediction. Purging protects retrospective train/test chronology.
    model_started=time.monotonic()
    ordered = frame.sort_values(time_col,kind='stable').copy()
    split = int(len(ordered)*0.8)
    cutoff = ordered.iloc[split][time_col]
    train = ordered.iloc[:split]
    train = train[train[label_available_col] < cutoff]
    test = ordered.iloc[split:]
    if len(train)<30 or len(test)<10 or (classification and train[target].nunique()<2):
        raise ValueError(f'{name}: insufficient matured training data')
    X, Xt = train[list(features)], test[list(features)]
    y, yt = train[target], test[target]
    pipeline = model_pipeline(X,classification); pipeline.fit(X,y)
    predicted = pipeline.predict_proba(Xt)[:,1] if classification else pipeline.predict(Xt)
    baseline = DummyClassifier(strategy='prior') if classification else DummyRegressor(strategy='mean')
    baseline.fit(X,y)
    bp = baseline.predict_proba(Xt)[:,1] if classification else baseline.predict(Xt)
    directory=out/'models'/name; directory.mkdir(parents=True,exist_ok=True)
    joblib.dump(pipeline,directory/'model.joblib')
    evidence=dict(model=name,prediction_time=time_col,features=list(features),cutoff=cutoff,
                  n_train=len(train),n_purged=split-len(train),test=metrics(yt,predicted,classification),
                  baseline=metrics(yt,bp,classification),synthetic_only=True,training_duration_seconds=time.monotonic()-model_started)
    save(directory/'metrics.json',evidence)
    policy_path=Path('monitoring/policy.json')
    threshold=json.loads(policy_path.read_text())['psi_alert_threshold'] if policy_path.exists() else 0.2
    save(directory/'drift.json',drift_report(X,Xt,threshold))
    scoring='roc_auc' if classification and yt.nunique()==2 else 'neg_mean_absolute_error'
    save(directory/'feature_importance.json',explain(pipeline,Xt,yt,scoring))
    save(directory/'individual_explanations.json',local_explanations(pipeline,Xt,X,classification))
    identity = 'claim_id' if name=='claim_denial' else 'encounter_id'
    preds=test[[identity,time_col]].copy();preds['actual']=yt
    preds['prediction']=predicted;preds['model_name']=name
    preds['scored_at']=datetime.now(timezone.utc).isoformat()
    preds.to_csv(directory/'predictions.csv',index=False)
    if classification:
        order=np.argsort(-predicted);k=max(1,int(len(test)*0.2))
        evidence['top_20pct_precision']=float(yt.iloc[order[:k]].mean())
        evidence['review_fraction']=k/len(test)
        save(directory/'metrics.json',evidence)
    return preds,evidence


def quality_checks(patients,encounters,events,claims):
    failures=[]
    for table,key in [(patients,'patient_id'),(encounters,'encounter_id'),(events,'event_id'),(claims,'claim_id')]:
        if table[key].isna().any() or table[key].duplicated().any():failures.append(f'{key}: duplicate/null')
        if not table.synthetic.astype(str).str.lower().eq('true').all():failures.append(f'{key}: non-synthetic')
    if not encounters.patient_id.isin(patients.patient_id).all():failures.append('orphan patients')
    for table in (claims,events):
        if not table.encounter_id.isin(encounters.encounter_id).all():failures.append('orphan encounters')
    if (encounters.discharge_ts < encounters.admission_ts).any():failures.append('negative encounter duration')
    if ((claims.paid_amount<0)|(claims.allowed_amount<claims.paid_amount)|(claims.billed_amount<claims.allowed_amount)).any():failures.append('financial inconsistency')
    return failures


def build(out: Path, patient_count=2000, seed=42):
    started=time.monotonic();out.mkdir(parents=True,exist_ok=True)
    save(out/'build_manifest.json',dict(status='running',synthetic_only=True))
    source=out/'source';manifest=generate_dataset(source,patient_count,seed)
    patients,encounters,events,claims=[pd.read_csv(source/f'{n}.csv') for n in ('patients','encounters','clinical_events','claims')]
    for frame,cols in [(encounters,['admission_ts','discharge_ts']),(events,['event_ts','ingested_at']),(claims,['claim_submit_ts','adjudicated_at'])]:
        for c in cols:frame[c]=pd.to_datetime(frame[c],utc=True,errors='coerce',format='ISO8601')
    failures=quality_checks(patients,encounters,events,claims)
    save(out/'quality_checks.json',dict(status='failed' if failures else 'passed',failures=failures))
    if failures:raise ValueError('; '.join(failures))
    event=events.sort_values(['ingested_at','event_id']).drop_duplicates(['encounter_id','source_event_key'])
    event['missing_ts']=event.event_ts.isna().astype(int);event['missing_dept']=event.department.isna().astype(int)
    event['late']=((event.ingested_at-event.event_ts).dt.total_seconds()>86400).astype(int)
    summary=event.groupby('encounter_id').agg(event_count=('event_id','size'),events_missing_timestamp=('missing_ts','sum'),events_missing_department=('missing_dept','sum'),events_arriving_over_24h_late=('late','sum'))
    totals=claims.assign(denied=claims.claim_status.eq('denied').astype(int)).groupby('encounter_id').agg(billed_amount=('billed_amount','sum'),allowed_amount=('allowed_amount','sum'),paid_amount=('paid_amount','sum'),denied_claim_count=('denied','sum'))
    frame=encounters.merge(patients.drop(columns='synthetic'),on='patient_id',validate='many_to_one').join(summary,on='encounter_id').join(totals,on='encounter_id')
    frame['patient_age_at_admission']=frame.admission_ts.dt.year-frame.birth_year
    frame['admission_hour']=frame.admission_ts.dt.hour;frame['admission_dow']=frame.admission_ts.dt.dayofweek;frame['admission_month']=frame.admission_ts.dt.month
    frame['readmission_label_available']=frame.discharge_ts+pd.Timedelta(days=30)
    # Last encounters need a full follow-up window in the declared source horizon.
    observed=frame[frame.readmission_label_available<=pd.Timestamp('2025-12-31',tz='UTC')]
    results={}
    rp,results['readmission_30d']=fit_model(observed,ADMISSION_FEATURES,'readmitted_30d','admission_ts','readmission_label_available','readmission_30d',out)
    lp,results['length_of_stay']=fit_model(frame,ADMISSION_FEATURES,'length_of_stay_hours','admission_ts','discharge_ts','length_of_stay',out,False)
    claim_frame=claims[claims.adjudicated_at.notna()].copy();claim_frame['denied']=claim_frame.claim_status.eq('denied').astype(int)
    claim_frame['billed_amount']=claim_frame.billed_amount.astype(float)
    cp,results['claim_denial']=fit_model(claim_frame,CLAIM_FEATURES,'denied','claim_submit_ts','adjudicated_at','claim_denial',out)
    # Compare held-out predictions and actuals at encounter/claim grain.
    frame=frame.merge(rp[['encounter_id','prediction']].rename(columns={'prediction':'readmission_probability'}),on='encounter_id',how='left',validate='one_to_one')
    frame=frame.merge(lp[['encounter_id','prediction']].rename(columns={'prediction':'length_of_stay_hours_predicted'}),on='encounter_id',how='left',validate='one_to_one')
    frame['length_of_stay_prediction_error_hours']=frame.length_of_stay_hours_predicted-frame.length_of_stay_hours
    frame['admission_date']=frame.admission_ts.dt.date
    reports=out/'reports';reports.mkdir(exist_ok=True)
    frame.to_csv(reports/'rpt_encounter_risk_scorecard.csv',index=False)
    crosswalk=pd.read_csv('warehouse/seeds/clinical_taxonomy_crosswalk.csv')
    event.merge(crosswalk.drop(columns='synthetic'),on=['source_system','source_code'],how='left',validate='many_to_one').to_csv(reports/'rpt_clinical_taxonomy.csv',index=False)
    queue=claim_frame.merge(cp[['claim_id','prediction']],on='claim_id',validate='one_to_one').rename(columns={'prediction':'denial_probability'})
    queue=queue.sort_values(['denial_probability','claim_id'],ascending=[False,True]);queue['review_rank']=range(1,len(queue)+1)
    queue.to_csv(reports/'rpt_claim_denial_queue.csv',index=False)
    quality=frame.groupby('admission_date').agg(encounter_count=('encounter_id','size'),clinical_event_count=('event_count','sum'),events_missing_timestamp=('events_missing_timestamp','sum'),events_missing_department=('events_missing_department','sum'),events_arriving_over_24h_late=('events_arriving_over_24h_late','sum'))
    for c in ['events_missing_timestamp','events_missing_department','events_arriving_over_24h_late']:quality[c+'_rate']=quality[c]/quality.clinical_event_count
    quality.to_csv(reports/'rpt_data_quality_overview.csv')
    frame.groupby(['admission_date','facility_id','service_line']).agg(encounter_count=('encounter_id','size'),length_of_stay_hours_avg=('length_of_stay_hours','mean'),readmitted_30d_rate=('readmitted_30d','mean'),billed_amount_total=('billed_amount','sum'),paid_amount_total=('paid_amount','sum')).to_csv(reports/'rpt_facility_daily_summary.csv')
    from healthcare_capstone.operations import build_operations
    from healthcare_capstone.edi import submission_segment, remittance_segment, parse_segments
    build_operations(encounters,reports)
    edi=out/'edi';edi.mkdir(exist_ok=True)
    subset=claims.head(50).to_dict('records')
    for filename,fn in [('claims_837_segments.x12',submission_segment),('remittance_835_segments.x12',remittance_segment)]:
        rows=[row for row in subset if filename.startswith('claims_') or row['claim_status'] != 'pending']
        text='\n'.join(fn(row) for row in rows)
        assert len(parse_segments(text))==len(rows)
        (edi/filename).write_text(text)
    drift_alerts=[dict(model=n,**x) for n in results for x in json.loads((out/'models'/n/'drift.json').read_text()) if x['status']!='ok']
    save(out/'alerts.json',dict(owner='analytics-platform-owner',action='Inspect input distributions and model coverage before refresh.',alerts=drift_alerts))
    save(out/'build_manifest.json',dict(status='passed',synthetic_only=True,seed=seed,rows=manifest['row_counts'],models=results,duration_seconds=time.monotonic()-started,cloud_execution_verified=False,powerbi_refresh_verified=False))
    return results


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=Path('data/demo'));p.add_argument('--patients',type=int,default=2000);p.add_argument('--seed',type=int,default=42)
    args=p.parse_args();print(json.dumps(build(args.output,args.patients,args.seed),indent=2,default=str))
if __name__=='__main__':main()
