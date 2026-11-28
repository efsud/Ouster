"""Recorded-data masking check; no tuning on masked positions."""
import json,hashlib,argparse
from pathlib import Path
import numpy as np
from .color_slope import bridge,associate
from .spatial_bridges import endpoint
from .reconstruction_layers import prediction

def run(snapshot,report):
    rows=[];matches=[]
    for site in snapshot['sites']:
        for gap in (5,10,20,30,60):
            pools={}
            sampled=0
            for index,tr in sorted(enumerate(site['tracks']),key=lambda z:hashlib.sha256(str((site['id'],z[0])).encode()).hexdigest()):
                if tr['class_type']!='2' or len(tr['points'])<15:continue
                p=np.asarray(tr['points'],float)
                if np.any(np.diff(p[:,0])>1.5) or p[-1,0]-p[0,0]<gap+6:continue
                start=(p[0,0]+p[-1,0]-gap)/2
                before=p[p[:,0]<=start];after=p[p[:,0]>=start+gap]
                a=endpoint(before.tolist(),True);b=endpoint(after.tolist(),False)
                if not a or not b:continue
                hidden=p[(p[:,0]>a['t'])&(p[:,0]<b['t'])]
                if not len(hidden):continue
                if sampled>=20:break
                sampled+=1
                errors={}
                simple=bridge(a,b,max_gap=90,max_residual=10)
                old=prediction(a,b,report,exact_join=True)
                for name,path in [('color_slope',simple['points'] if simple else None),('reference_kinematic',old)]:
                    if path is not None:
                        q=np.asarray(path);errors[name]=float(np.mean(abs(np.interp(hidden[:,0],q[:,0],q[:,1])-hidden[:,1])))
                rows.append(dict(site=site['id'],gap_s=gap,track=index,errors=errors))
                direction=tr['direction'];left,right=pools.setdefault(direction,([],[]))
                left.append(dict(a,truth=index,direction=direction));right.append(dict(b,truth=index,direction=direction))
            for direction,(left,right) in pools.items():
                accepted=associate(left,right,max_gap=90,max_residual=10)
                matches.append(dict(site=site['id'],gap_s=gap,direction=direction,eligible=len(left),matched=len(accepted),correct=sum(left[m['left']]['truth']==right[m['right']]['truth'] for m in accepted)))
    summary={}
    for name in ('color_slope','reference_kinematic'):
        values=[r['errors'][name] for r in rows if name in r['errors']]
        common=[r['errors'][name] for r in rows if len(r['errors'])==2]
        summary[name]=dict(eligible=len(rows),accepted=len(values),mae_m=float(np.mean(values)) if values else None,p95_case_mae_m=float(np.percentile(values,95)) if values else None,common_n=len(common),common_mae_m=float(np.mean(common)) if common else None)
    return dict(summary=summary,association={k:sum(r[k] for r in matches) for k in ('eligible','matched','correct')},cases=rows,matching=matches,limitations=['Retrospective latest-window check, no parameter tuning; repeated gap lengths are correlated.','Same-sensor masked identity truth does not validate real cross-sensor identity.','No fully hidden vehicles can be recovered.'])
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--snapshot',required=True);p.add_argument('--report',required=True);p.add_argument('--output',required=True);a=p.parse_args()
 raw=Path(a.snapshot).read_bytes();r=run(json.loads(raw),json.loads(Path(a.report).read_text()));r['snapshot_sha256']=hashlib.sha256(raw).hexdigest();Path(a.output).parent.mkdir(parents=True,exist_ok=True);Path(a.output).write_text(json.dumps(r,indent=2));print(json.dumps({k:r[k] for k in ('summary','association')}))
