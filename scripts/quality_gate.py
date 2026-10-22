"""Fail closed on stale data, failed tests, or unacceptable source quality."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd


def evaluate(directory, policy, now=None):
    now=now or datetime.now(timezone.utc)
    failures=[]
    required=['quality_checks.json','build_manifest.json','reports/rpt_data_quality_overview.csv']
    for name in required:
        if not (directory/name).exists():failures.append('missing evidence: '+name)
    if failures:return failures
    if json.loads((directory/'quality_checks.json').read_text())['status']!='passed':failures.append('blocking source quality tests')
    if json.loads((directory/'build_manifest.json').read_text())['status']!='passed':failures.append('incomplete pipeline run')
    age=(now.timestamp()-(directory/'build_manifest.json').stat().st_mtime)/3600
    if age>policy['freshness_hours']:failures.append('stale build evidence')
    q=pd.read_csv(directory/'reports/rpt_data_quality_overview.csv')
    total=q.clinical_event_count.sum()
    if total<=0:failures.append('no clinical events')
    else:
        for col,key in [('events_missing_timestamp','max_missing_timestamp_rate'),('events_missing_department','max_missing_department_rate'),('events_arriving_over_24h_late','max_late_arrival_rate')]:
            if q[col].sum()/total>policy[key]:failures.append(col+' exceeds threshold')
    return failures


def main():
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,default=Path('data/demo'));p.add_argument('--policy',type=Path,default=Path('monitoring/policy.json'));a=p.parse_args()
    policy=json.loads(a.policy.read_text());failures=evaluate(a.input,policy)
    alert=dict(status='failed' if failures else 'passed',failures=failures,owner=policy['owner'],response=policy['response'])
    (a.input/'quality_gate.json').write_text(json.dumps(alert,indent=2));print(json.dumps(alert))
    raise SystemExit(bool(failures))
if __name__=='__main__':main()
