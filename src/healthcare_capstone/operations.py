"""Synthetic ADT/transport/EVS reconciliation and taxonomy demonstration."""
from pathlib import Path
import pandas as pd


def reconcile_beds(events):
    required=['administrative_discharge_ts','transport_departure_ts','cleaning_complete_ts']
    result=events.copy()
    for c in required:
        result[c]=pd.to_datetime(result[c],utc=True,errors='coerce',format='ISO8601')
    # Unknown milestones mean unknown readiness, never administrative discharge alone.
    complete=result[required].notna().all(axis=1)
    result['bed_ready_ts']=result[required].max(axis=1).where(complete)
    result['turnover_minutes']=(result.bed_ready_ts-result.administrative_discharge_ts).dt.total_seconds()/60
    result['readiness_status']=complete.map({True:'ready',False:'incomplete'})
    return result


def build_operations(encounters,out):
    out.mkdir(parents=True,exist_ok=True)
    x=encounters[['encounter_id','facility_id','admission_ts','discharge_ts']].copy()
    # Explicit synthetic scenarios, not inferred real ADT/EVS events.
    x['administrative_discharge_ts']=x.discharge_ts
    x['transport_departure_ts']=x.discharge_ts+pd.Timedelta(minutes=20)
    x['cleaning_complete_ts']=x.discharge_ts+pd.Timedelta(minutes=65)
    x['ed_arrival_ts']=x.admission_ts-pd.Timedelta(minutes=150)
    x['ed_departure_ts']=x.admission_ts
    x.loc[x.index%11==0,'cleaning_complete_ts']=pd.NaT
    x['synthetic']=True
    ready=reconcile_beds(x)
    ready['ed_dwell_minutes']=(ready.ed_departure_ts-ready.ed_arrival_ts).dt.total_seconds()/60
    ready.to_csv(out/'bed_milestones.csv',index=False)
    return ready
