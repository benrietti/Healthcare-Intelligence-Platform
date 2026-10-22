"""Render a self-contained review page from a completed local build."""
import argparse
import html
import json
from pathlib import Path
import pandas as pd
p=argparse.ArgumentParser();p.add_argument('--input',type=Path,default=Path('data/demo'));a=p.parse_args();root=a.input
manifest=json.loads((root/'build_manifest.json').read_text());queue=pd.read_csv(root/'reports/rpt_claim_denial_queue.csv');quality=pd.read_csv(root/'reports/rpt_data_quality_overview.csv')
sections=[]
for name,model in manifest['models'].items():
 values=''.join('<li>'+html.escape(k)+': '+html.escape(str(round(v,4) if isinstance(v,float) else v))+'</li>' for k,v in model['test'].items())
 sections.append('<section><h2>'+html.escape(name.replace('_',' ').title())+'</h2><ul>'+values+'</ul><p>Compared with a simple baseline; these are synthetic holdout results.</p></section>')
cols=['review_rank','claim_id','payer','billed_amount','denial_probability','authorization_present','documentation_complete']
page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Healthcare Platform Build Results</title><style>body{font:16px system-ui;background:#f5f9f9;color:#16313c;margin:0;padding:32px;max-width:1200px;margin:auto}h1,h2{color:#087e82}section{background:white;border:1px solid #dce5e7;border-radius:14px;padding:22px;margin:20px 0;overflow:auto}table{border-collapse:collapse;width:100%;font-size:13px}td,th{border-bottom:1px solid #ddd;padding:8px;text-align:left}input{padding:10px;width:300px}small{color:#52656c}</style><h1>Healthcare Intelligence Platform</h1><p>Reproducible local build results · synthetic data only</p><small>This review page is generated from CSV and JSON outputs. It is not a Power BI render or proof of cloud deployment.</small>'''
page+=''.join(sections)
page+='<section><h2>Claim Denial Review Queue</h2><p>Ranked by held-out predicted probability; review rank is not a clinical or financial recommendation.</p><input id="search" placeholder="Filter by claim or payer">'+queue[cols].head(100).to_html(index=False,escape=True,table_id='queue')+'</section>'
page+='<section><h2>Pipeline Data Quality</h2>'+quality.tail(20).to_html(index=False,escape=True)+'</section>'
page+='''<script>document.getElementById('search').addEventListener('input',e=>{document.querySelectorAll('#queue tbody tr').forEach(r=>{r.hidden=!r.textContent.toLowerCase().includes(e.target.value.toLowerCase())})})</script></html>'''
(root/'review.html').write_text(page)
