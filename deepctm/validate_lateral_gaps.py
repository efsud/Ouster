"""Raw recorded 2D masking audit for experimental same-ID lateral gaps.

Uses an owned in-memory SQLite backup and does not modify the collector database.
Only aggregate results/case scores are saved, not the temporary raw replay.
"""
import argparse,json,sqlite3,time,hashlib
from pathlib import Path
import numpy as np
from .florida_rolling import build
from .archive_extension import cases
from .same_id_gaps import candidates
from .lateral_gap import lateral_curve,supports
from .reconstruction_layers import prediction
from .reconstruction_study import metrics,summarize

def identity_hash(site,key):
    return hashlib.sha256(json.dumps([site,key[:2]]).encode()).hexdigest()

def run(region,report,limit=12,after=None,excluded_ids=(),max_gap=30,deadline=None):
    from dashboard.server import sites
    from .buffer_snapshot import copy_buffer
    root=Path(__file__).resolve().parents[1]
    memory=copy_buffer(root/f'data/{region}-rolling/buffer.sqlite3',max_seconds=min(30,max(.1,deadline-time.time())) if deadline is not None else 30)
    raw={};region_name='Florida' if region=='florida' else 'Toronto'
    def observe(site,key,points):
        raw[(site['id'],tuple(key),round(points[0][0],2))]=points
    end=time.time();axes=json.loads((root/'config/reconstruction/corridor-road-axes.json').read_text())
    snapshot=build(memory,[s for s in sites() if s['region']==region_name],end,road_axes=axes,track_observer=observe,processing_interval_s=.5);memory.close()
    excluded_ids=set(excluded_ids)
    for site in snapshot['sites']:
        site['tracks']=[tr for tr in site['tracks'] if (after is None or tr['receipt_start']>=after) and identity_hash(site['id'],tr['source_key']) not in excluded_ids]
    results=[];missing=0;stopped=False
    for rank,site,tr,gap,(a,b,truth) in cases(snapshot,'test',limit):
        if deadline is not None and time.time()>=deadline:stopped=True;break
        if gap>max_gap:continue
        points=raw.get((site['id'],tuple(tr['source_key']),round(tr['receipt_start'],2)))
        if points is None:missing+=1;continue
        mapping={round(p[0]-snapshot['start'],2):p for p in points}
        left=[p for p in tr['points'] if p[0]<=a['t']];right=[p for p in tr['points'] if p[0]>=b['t']]
        pa,pb=mapping[left[-1][0]],mapping[right[0][0]]
        if not 2<abs(pb[2]-pa[2])<=7.2:continue
        from .endpoint_context import select
        before=dict(tr,points=left,direction='eastbound' if left[-1][1]>=left[0][1] else 'westbound',movement={'state':'unknown'},sensor_end=pa[4].isoformat(),lateral_end_m=pa[2],
                    lateral_end_context=[[p[0],mapping[p[0]][2]] for p in select(left,True)])
        after_fragment=dict(tr,points=right,direction='eastbound' if right[-1][1]>=right[0][1] else 'westbound',movement={'state':'unknown'},sensor_start=pb[4].isoformat(),lateral_start_m=pb[2],
                   lateral_start_context=[[p[0],mapping[p[0]][2]] for p in select(right,False)])
        visible_ok=all(abs(p[-1][1]-p[0][1])>=3 and abs(p[-1][1]-p[0][1])>=.7*sum(abs(v[1]-u[1]) for u,v in zip(p,p[1:])) for p in (left,right))
        admitted=list(candidates({'tracks':[before,after_fragment]},include_same_class=True,allow_lateral_motion=True)) if visible_ok else []
        row={'rank':rank,'identity_hash':identity_hash(site['id'],tr['source_key']),'site':site['id'],'gap_s':gap,'admitted':bool(admitted),'accepted':False}
        if admitted:
            c=admitted[0];pred=prediction(c['a'],c['b'],report,exact_join=True)
            if pred is not None:
                accepted,evidence=supports(before,after_fragment,pred);row['evidence']=evidence
                if accepted:
                    lateral,_=lateral_curve(before,after_fragment,np.asarray(pred)[:,0]);pred=np.asarray(pred);pred[:,1]*=1 if tr['direction']=='eastbound' else -1
                    hidden=[p for p in points if a['t']<round(p[0]-snapshot['start'],2)<b['t']]
                    error=[abs(float(np.interp(round(p[0]-snapshot['start'],2),lateral[:,0],lateral[:,1]))-p[2]) for p in hidden]
                    row.update(accepted=True,metrics=metrics(pred,truth,report['calibration']['parameters']),lateral_mae_m=float(np.mean(error)))
        results.append(row)
    accepted=[r for r in results if r['accepted']]
    return {'state':'deadline_reached' if stopped else 'complete','created_at':time.time(),'window':[snapshot['start'],snapshot['end']],'test_after':after,'processing_interval_s':.5,'transform_manifest':snapshot.get('transform_manifest'),'max_gap_s':max_gap,'missing_source_tracks':missing,'eligible_lateral_masks':len(results),'accepted':len(accepted),
            'parameters':report['calibration']['parameters'],'implementation_sha256':{name:hashlib.sha256((root/'deepctm'/name).read_bytes()).hexdigest() for name in ('validate_lateral_gaps.py','lateral_gap.py','same_id_gaps.py','trajectory_reconstruction.py')},
            'quality':summarize([r['metrics'] for r in accepted]),'lateral_mae_m':float(np.mean([r['lateral_mae_m'] for r in accepted])) if accepted else None,'cases':results,
            'limitations':['Development masks of observed same-ID tracks; no cross-sensor identity evidence.','Road region and lateral projection provisional.','No production gate changed.','Multiple mask lengths may share a vehicle.']}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--region',choices=['florida','finch'],required=True);p.add_argument('--report',required=True);p.add_argument('--output',required=True);p.add_argument('--protocol');p.add_argument('--after',type=float);a=p.parse_args()
    protocol=json.loads(Path(a.protocol).read_text()) if a.protocol else {}
    after=max(a.after or 0,protocol.get('after',0)) or None
    result=run(a.region,json.loads(Path(a.report).read_text()),after=after,excluded_ids=protocol.get('excluded_ids',{}).get(a.region,[]),max_gap=protocol.get('max_gap_s',30));Path(a.output).parent.mkdir(parents=True,exist_ok=True);Path(a.output).write_text(json.dumps(result,indent=2));print({k:v for k,v in result.items() if k!='cases'})
