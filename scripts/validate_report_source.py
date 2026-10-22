"""Static validation of the new Power BI page; not a Desktop rendering test."""
import json
from pathlib import Path
root=Path('powerbi/Healthcare Intelligence Platform.SemanticModel/definition')
report=Path('powerbi/Healthcare Intelligence Platform.Report/definition')
tables={p.stem:p.read_text() for p in (root/'tables').glob('*.tmdl')}
for name in ['rpt_claim_denial_queue','rpt_model_drift']:
    if 'ref table '+name not in (root/'model.tmdl').read_text():raise ValueError('Unregistered semantic table '+name)

def walk(obj):
    if isinstance(obj,dict):
        for kind in ['Column','Measure']:
            if kind in obj:
                item=obj[kind];table=item['Expression']['SourceRef']['Entity'];prop=item['Property'];definition=tables[table]
                if ('column '+prop) not in definition and ("measure '"+prop+"'") not in definition:raise ValueError('Unknown field '+table+'.'+prop)
        for value in obj.values():walk(value)
    elif isinstance(obj,list):
        for value in obj:walk(value)

for path in Path('powerbi').rglob('*.json'):json.loads(path.read_text())
page='ReportSectionDenialAndMonitoring'
if page not in json.loads((report/'pages/pages.json').read_text())['pageOrder']:raise ValueError('Page missing from navigation')
for path in (report/'pages'/page).rglob('visual.json'):
    data=json.loads(path.read_text());walk(data)
    if data['visual']['visualType']=='card' and 'Values' not in data['visual']['query']['queryState']:raise ValueError('Wrong card data role')
print('Power BI source bindings passed; Desktop rendering and refresh still required.')
