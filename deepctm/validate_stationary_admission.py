"""Test previously excluded negative-displacement quiet endpoints by masking.

Never treat endpoint stationarity as proof of hidden stationarity: score the
entire concealed observed interval, including any motion inside it.
"""
import json,hashlib,argparse
from pathlib import Path
import numpy as np
from .spatial_bridges import endpoint
from .stationary_plateau import estimate
from .reconstruction_study import metrics,summarize
from .corridor_campaign import subset,earlier_ids,identity,atomic


def evaluate(s,params):
    rows=[];evaluated=0
    for site in s['sites']:
        if site['id']=='OBC-AG-SA-C257223':continue
        for tr in site['tracks']:
            if tr['class_type']!='2':continue
            p=np.asarray(tr['points'],float).copy()
            if len(p)<12 or np.any(np.diff(p[:,0])<=0) or np.any(np.diff(p[:,0])>1.5):continue
            sign=1 if tr['direction']=='eastbound' else -1;p[:,1]*=sign
            # Fixed offsets; no truth-based selection of a stopped interval.
            for gap in (5,10,20):
                for start in np.arange(p[0,0]+3,p[-1,0]-gap-3,10):
                    left=p[p[:,0]<=start];right=p[p[:,0]>=start+gap]
                    a=endpoint(left.tolist(),True);b=endpoint(right.tolist(),False)
                    if a is None or b is None:continue
                    evaluated+=1
                    if b['x']>=a['x']:continue
                    pred=estimate(a,b,same_identity=True)
                    if pred['state']!='candidate':continue
                    truth=p[(p[:,0]>a['t'])&(p[:,0]<b['t'])]
                    if len(truth)<3:continue
                    rows.append(dict(site=site['id'],identity_hash=hashlib.sha256(identity(site,tr).encode()).hexdigest(),gap_s=gap,metrics=metrics(pred['points'],truth,params)))
    quality=summarize([r['metrics'] for r in rows]);ids=len({r['identity_hash'] for r in rows})
    return dict(evaluated=evaluated,accepted=len(rows),distinct_ids=ids,quality=quality,cases=rows,qualifies=bool(ids>=20 and quality.get('mae_m',999)<=.25 and quality.get('speed_mae_mps',999)<=.2 and quality.get('physics_violation',1)==0 and quality.get('stop_precision',0)==1))


def run(output):
    raw=Path('data/florida-rolling/snapshot.json').read_bytes();s=json.loads(raw);r=json.load(open('data/reconstruction/word-v1-collection/evaluation-001/report.json'));path=Path(output)
    atomic(path/'stationary-protocol.json',dict(snapshot_sha256=hashlib.sha256(raw).hexdigest(),window=[s['start'],s['end']],split=s['start']+1800,embargo_s=30,thresholds=dict(min_distinct_ids=20,max_position_mae_m=.25,max_speed_mae_mps=.2,stop_precision=1),policy='Existing stationary plateau limits, <=30s, <=10cm endpoint separation, quiet visible contexts; no tuning. Hattaway remains excluded.'))
    dev=evaluate(subset(s,0,1770),r['calibration']['parameters']);atomic(path/'stationary-development.json',dev)
    test=evaluate(subset(s,1830,3600,earlier_ids(s,1800)),r['calibration']['parameters']);atomic(path/'stationary-test.json',test)
    out=dict(development={k:v for k,v in dev.items() if k!='cases'},test={k:v for k,v in test.items() if k!='cases'},eligible=dev['qualifies'] and test['qualifies'],limitations=['Conditional same-ID masks; timestamp, lateral and identity admission gates remain unchanged.','No cross-sensor association validation. Repeated masks from the same vehicle are correlated.'])
    atomic(path/'stationary-validation.json',out);print(json.dumps(out),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);run(p.parse_args().output)
