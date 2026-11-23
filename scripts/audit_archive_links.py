"""Count hypotheses on real adjacent sensors, explicitly without accuracy claims."""
import json
from pathlib import Path
from deepctm.spatial_bridges import reconstruct
from deepctm.archive_extension import calibrated
folder=Path('data/reconstruction/archive-extension/evaluation');r=json.loads((folder/'report.json').read_text())
assert r['state']=='complete'
s=json.loads(Path('data/reconstruction/archive-extension/pm/snapshot.json').read_text());selected=r['selected_association'];ratio=r['association_calibration']['time_ratio'];out={}
for method in dict.fromkeys(['current',selected]):
 callback=None if method=='current' else lambda a,b:calibrated(a,b,ratio,float(method.split('_')[1]))
 result=reconstruct(s,association_method='feasible',matcher=callback)
 out[method]=[{**{k:l.get(k) for k in ('names','direction','departure_candidates','arrival_candidates','unmatched_departures','unmatched_arrivals','reason')},'estimated_matches':len(l['paths'])} for l in result['links']]
 print(method,sum(l['estimated_matches'] for l in out[method]),flush=True)
(folder/'real-link-audit.json').write_text(json.dumps({'results':out,'warning':'Counts of hypotheses only. No identity ground truth exists between these sensors; more lines are not evidence of more correct matches.'},indent=2))
