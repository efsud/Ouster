"""Raw-clock/2D masking test for a fixed local lateral recovery policy."""
import json,time,hashlib,math,sqlite3,argparse
from pathlib import Path
from statistics import median
from datetime import datetime
from collections import defaultdict,Counter
import numpy as np
from .endpoint_context import select
from .reconstruction_study import masked_case,metrics,summarize
from .reconstruction_layers import prediction
from .local_lateral_recovery import reconstruct
from .lateral_gap import lateral_curve
from .corridor_campaign import identity,earlier_ids,subset,atomic

def run(folder):
    from dashboard.server import sites
    from .florida_rolling import geometry
    root=Path(__file__).resolve().parents[1];folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    raw=(root/'data/florida-rolling/snapshot.json').read_bytes();s=json.loads(raw);report=json.loads((root/'data/reconstruction/word-v1-collection/evaluation-001/report.json').read_text())
    mid=(s['end']-s['start'])/2
    protocol=dict(created_at=time.time(),snapshot_sha256=hashlib.sha256(raw).hexdigest(),window=[s['start'],s['end']],split=s['start']+mid,embargo_s=30,max_gap_s=10,
        gates='At least 20 distinct new test identities across two sites; longitudinal MAE <=3m, speed MAE <=1m/s, p95 case MAE <=10m, lateral MAE <=0.75m, zero physics violations. Same limits on development; no tuning after test.',test_opened=False)
    atomic(folder/'protocol.json',protocol)
    meta={m['id']:m for m in geometry([m for m in sites() if m['region']=='Florida'])}
    from .buffer_snapshot import copy_buffer
    db=copy_buffer(root/'data/florida-rolling/buffer.sqlite3',max_seconds=30)
    def observation(site,tr,t):
        target=s['start']+t
        row=db.execute('SELECT payload FROM frames WHERE site=? AND session=? AND received BETWEEN ? AND ? ORDER BY abs(received-?) LIMIT 1',(site['id'],tr['source_key'][0],target-.02,target+.02,target)).fetchone()
        if row is None:return None
        event=json.loads(row[0]);frame=event.get('frame',{});obj=next((o for o in frame.get('objects',[]) if str(o.get('id'))==str(tr['source_key'][1])),None)
        stamp=frame.get('timestamp') or event.get('timestamp')
        if obj is None or not stamp:return None
        m=meta[site['id']];angle=math.radians(m.get('preview_rotation_deg',220))-math.radians(site.get('projection_bearing_deg',math.degrees(m['bearing'])))
        x=float(obj['centerX']);y=float(obj['centerY'])*(-1 if m.get('preview_mirror_y') else 1)
        return stamp,math.sin(angle)*x+math.cos(angle)*y
    def evaluate(part):
        rows=[];missing=0;rejections=Counter()
        for site in part['sites']:
            # Full-track lateral displacement is used for stratified sampling
            # only. Neither it nor the full movement label enters reconstruction.
            pool=defaultdict(list)
            for tr in site['tracks']:
                if tr['class_type']!='2':continue
                rank=hashlib.sha256(identity(site,tr).encode()).hexdigest()
                for gap in (5,10):
                    case=masked_case(tr,gap)
                    if case is not None:
                        stratum=abs(tr.get('lateral_end_m',0)-tr.get('lateral_start_m',0))>1
                        pool[tr['direction'],gap,stratum].append((rank,tr,gap,case))
            selected=[r for group in pool.values() for r in sorted(group,key=lambda r:r[0])[:60]]
            for rank,tr,gap,(a,b,truth) in selected:
                left=[p for p in tr['points'] if p[0]<=a['t']];right=[p for p in tr['points'] if p[0]>=b['t']]
                cache={}
                def get(t):
                    if t not in cache:cache[t]=observation(site,tr,t)
                    return cache[t]
                contexts=[select(left,True),select(right,False)]
                vals=[[get(p[0]) for p in context] for context in contexts]
                if any(v is None for vv in vals for v in vv):missing+=1;continue
                before=dict(tr,points=left,movement={'state':'unknown'},sensor_end=vals[0][-1][0],lateral_end_m=median(v[1] for v in vals[0]),lateral_end_context=[[p[0],v[1]] for p,v in zip(contexts[0],vals[0])])
                after=dict(tr,points=right,movement={'state':'unknown'},sensor_start=vals[1][0][0],lateral_start_m=median(v[1] for v in vals[1]),lateral_start_context=[[p[0],v[1]] for p,v in zip(contexts[1],vals[1])])
                visible_ok=True
                for frag in (before,after):
                    pp=frag['points'];net=pp[-1][1]-pp[0][1];travel=sum(abs(v[1]-u[1]) for u,v in zip(pp,pp[1:]));frag['direction']='eastbound' if net>0 else 'westbound'
                    visible_ok &= abs(net)>=3 and abs(net)>=.7*travel
                row=dict(site=site['id'],identity_hash=rank,gap_s=gap,accepted=False)
                paths=reconstruct(dict(site,tracks=[before,after]),lambda aa,bb:prediction(aa,bb,report,exact_join=True),audit=lambda reason:rejections.update([reason])) if visible_ok else []
                if paths:
                    pred=np.asarray(paths[0]['points']);lat,_=lateral_curve(before,after,pred[:,0]);actual=[get(float(p[0])) for p in truth]
                    if any(v is None for v in actual):missing+=1;continue
                    lat_error=float(np.mean([abs(np.interp(p[0],lat[:,0],lat[:,1])-v[1]) for p,v in zip(truth,actual)]))
                    pred[:,1]*=1 if tr['direction']=='eastbound' else -1
                    row.update(accepted=True,metrics=metrics(pred,truth,report['calibration']['parameters']),lateral_mae_m=lat_error)
                rows.append(row)
        accepted=[r for r in rows if r['accepted']];q=summarize([r['metrics'] for r in accepted]);ids={r['identity_hash'] for r in accepted}
        lat=float(np.mean([r['lateral_mae_m'] for r in accepted])) if accepted else None
        # Explicit boolean expression avoids treating an unavailable metric as a pass.
        qualifies=bool(len(ids)>=20 and len({r['site'] for r in accepted})>=2 and q.get('mae_m',1e9)<=3 and q.get('speed_mae_mps',1e9)<=1 and q.get('p95_case_mae_m',1e9)<=10 and q.get('physics_violation',1)==0 and lat is not None and lat<=.75)
        return dict(evaluated=len(rows),missing_raw=missing,accepted=len(accepted),distinct_ids=len(ids),quality=q,lateral_mae_m=lat,qualifies=qualifies,rejections=dict(rejections),cases=rows)
    try:
        dev=evaluate(subset(s,0,mid-30));atomic(folder/'development.json',dev)
        protocol.update(test_opened=True,policy_frozen=True);atomic(folder/'protocol.json',protocol)
        test=evaluate(subset(s,mid+30,s['end']-s['start'],earlier_ids(s,mid)));atomic(folder/'test.json',test)
    finally:db.close()
    result=dict(state='complete',protocol=protocol,development={k:v for k,v in dev.items() if k!='cases'},test={k:v for k,v in test.items() if k!='cases'},deployment_eligible=dev['qualifies'] and test['qualifies'],limitations=['Known same-sensor identity masking only; not new-ID matching.','Stratified sample favors tracks with lateral motion; acceptance is not corridor-wide recall.','Repeated 5/10s masks are correlated; road geometry remains provisional.','Actual SDK timestamps and lateral context are used, not fabricated clocks.'])
    atomic(folder/'report.json',result);print(json.dumps(result),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();run(a.output)
