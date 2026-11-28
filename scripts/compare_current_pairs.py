"""Freeze the same observed window; compare all actual pairs without truth claims."""
import json,time
from pathlib import Path
from deepctm.reconstruction_layers import generate
folder=Path('data/reconstruction/all-florida');s=json.loads(Path('data/florida-rolling/snapshot.json').read_text());r=json.loads(Path('data/reconstruction/word-v1-collection/evaluation-001/report.json').read_text());policy=json.loads(Path('config/reconstruction/florida-endpoint-speed.json').read_text())
(folder/'comparison-snapshot.json').write_text(json.dumps(s,separators=(',',':')))
out={}
for name,method in [('current',None),('screened','strict_physics_v1')]:
 result=generate(s,r,endpoint_policy=policy['parameters'],endpoint_excluded_sites=policy.get('excluded_sites',[]),association_policy=method)
 (folder/(name+'-layers.json')).write_text(json.dumps(result,separators=(',',':')))
 out[name]=[{**{k:v for k,v in l.items() if k!='diagnostics'},'displayed':sum(p['sites']==l['sites'] and p['direction']==l['direction'] for p in result['between_intersections'])} for l in result['association_diagnostics']]
 print(name,len(result['within_intersection']),len(result['between_intersections']),flush=True)
(folder/'current-pair-comparison.json').write_text(json.dumps({'created_at':time.time(),'window':[s['start'],s['end']],'results':out,'warning':'Hypothesis counts, not verified correct matches'},indent=2))
