"""Paired hidden-observation reconstruction with bounded delivery correction.

Both estimators hide identical observations. Source selection is conditional on
continuous corrected tracks, reported separately for affected/unaffected cases.
"""
import json,time,argparse,hashlib
from pathlib import Path
from collections import defaultdict
import numpy as np
from .florida_rolling import build
from .buffer_snapshot import copy_buffer
from .corridor_campaign import subset,earlier_ids,identity,atomic
from .spatial_bridges import endpoint
from .reconstruction_layers import prediction
from .reconstruction_study import summarize,metrics


def evaluate(snapshot,report):
    rows=[]
    for site in snapshot['sites']:
        candidates=defaultdict(list)
        for tr in site['tracks']:
            if tr['class_type']!='2':continue
            p=np.asarray(tr['points'],float).copy();original=np.asarray(tr['original_receipt_offsets_s'])
            if len(p)<12 or np.any(np.diff(p[:,0])<=0) or np.any(np.diff(p[:,0])>1.5):continue
            rank=hashlib.sha256(identity(site,tr).encode()).hexdigest()
            for gap in (5,10,20):
                for fraction in (.25,.5,.75):
                    cut=p[0,0]+(p[-1,0]-p[0,0]-gap)*fraction
                    i=np.searchsorted(p[:,0],cut);j=np.searchsorted(p[:,0],cut+gap)
                    if i<4 or j+4>=len(p) or j-i<3:continue
                    affected=bool(np.max(abs(p[max(0,i-4):j+5,0]-original[max(0,i-4):j+5]))>.1)
                    candidates[gap,affected].append((rank,site,tr,i,j))
        for (gap,affected),pool in sorted(candidates.items()):
            # Fixed cap and deterministic order; neither error nor hidden motion
            # chooses cases. Counts are masks, not independent vehicles.
            for rank,_,tr,i,j in sorted(pool,key=lambda r:(r[0],r[3]))[:150]:
                points=np.asarray(tr['points'],float).copy();sign=1 if tr['direction']=='eastbound' else -1
                points[:,1]*=sign;received=points.copy();received[:,0]=tr['original_receipt_offsets_s']
                row=dict(site=site['id'],identity_hash=rank,gap_s=gap,affected=affected,metrics={})
                for label,p in [('receipt',received),('corrected',points)]:
                    a=endpoint(p[:i+1].tolist(),True);b=endpoint(p[j:].tolist(),False)
                    if not a or not b or not 0<b['t']-a['t']<=30:continue
                    pred=prediction(a,b,report,exact_join=True)
                    if pred is None:continue
                    truth=p[i+1:j]
                    row['metrics'][label]=metrics(np.asarray(pred),truth,report['calibration']['parameters'])
                rows.append(row)
    result={}
    for affected in (True,False):
        chosen=[r for r in rows if r['affected']==affected];common=[r for r in chosen if len(r['metrics'])==2]
        result[str(affected)]=dict(masks=len(chosen),distinct_ids=len({r['identity_hash'] for r in chosen}),common=len(common),
            methods={label:dict(accepted=sum(label in r['metrics'] for r in chosen),quality=summarize([r['metrics'][label] for r in chosen if label in r['metrics']]),common=summarize([r['metrics'][label] for r in common])) for label in ('receipt','corrected')})
    return dict(summary=result,cases=rows)


def run(output):
    from dashboard.server import sites
    path=Path(output);path.mkdir(parents=True,exist_ok=True)
    report=json.load(open('data/reconstruction/word-v1-collection/evaluation-001/report.json'))
    end=json.load(open('data/florida-rolling/snapshot.json'))['end']
    atomic(path/'protocol.json',dict(created_at=time.time(),window=[end-3600,end],split=end-1800,embargo_s=30,policy='Fixed bounded local timing correction; no parameter tuning. Receipt anchors on both sides; <=1% rate error, <=15s delivery delay, <=60s span; duplicate/reset clocks are not repaired.',gates='On development and later-ID test: >=20 affected IDs, more accepted affected cases, common affected position MAE no worse, no physics violations; no loss of raw rows. Unaffected results must not regress materially.'))
    print('copying buffer',flush=True);db=copy_buffer('data/florida-rolling/buffer.sqlite3')
    try:
        print('building candidate',flush=True)
        s=build(db,[x for x in sites() if x['region']=='Florida'],end,road_axes=json.load(open('config/reconstruction/corridor-road-axes.json')),time_basis='receipt_debursted',processing_interval_s=.5)
    finally:db.close()
    Path('/tmp/florida-debursted-candidate.json').write_text(json.dumps(s))
    atomic(path/'clock-audit.json',dict(window=[s['start'],s['end']],sites={x['id']:dict(frames=x['frames'],tracks=len(x['tracks']),clock_audit=x['clock_audit']) for x in s['sites']}))
    print('evaluating development',flush=True);dev=evaluate(subset(s,0,1770),report);atomic(path/'development.json',dev)
    print('evaluating later excluded-ID test',flush=True);test=evaluate(subset(s,1830,3600,earlier_ids(s,1800)),report);atomic(path/'test.json',test)
    def qualifies(r):
        a=r['summary']['True'];m=a['methods'];u=r['summary']['False']['methods']
        return bool(a['distinct_ids']>=20 and a['common']>=20 and m['corrected']['accepted']>m['receipt']['accepted'] and m['corrected']['common'].get('mae_m',1e9)<=m['receipt']['common'].get('mae_m',0) and m['corrected']['quality'].get('physics_violation',1)==0 and u['corrected']['common'].get('mae_m',1e9)<=u['receipt']['common'].get('mae_m',0)+.01)
    result=dict(state='complete',window=[s['start'],s['end']],development=dev['summary'],test=test['summary'],eligible=qualifies(dev) and qualifies(test),limitations=['Cases selected from corrected continuous tracks; not corridor-wide recall.','Exactly the same observed positions hidden in each time basis; timestamps are anchored estimates.','Absolute clock offsets and cross-sensor identities unverified.','The original 12:08 raw window has expired from the 90-minute buffer; saved audit remains. This validates the same delay mechanism on later data.'])
    atomic(path/'report.json',result);print(json.dumps(result),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);run(p.parse_args().output)
