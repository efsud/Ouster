"""Hide complete receipt-time intervals before the real reconstruction pipeline.

All sites lose frames together, including phase samples. No hidden observations
are passed to build/generate. Scoring uses continuous recorded local fragments;
vehicles entirely inside a hidden interval cannot be recovered from endpoints.
"""
import argparse,json,sqlite3,time
from pathlib import Path
import numpy as np
from .florida_rolling import build
from .reconstruction_layers import generate
from .reconstruction_study import metrics,summarize
from .corridor_campaign import atomic

def run(region,output):
    from dashboard.server import sites
    root=Path(__file__).resolve().parents[1]
    src=sqlite3.connect(f'file:{root}/data/{region}-rolling/buffer.sqlite3?mode=ro',uri=True,timeout=20)
    db=sqlite3.connect(':memory:')
    try:src.backup(db,pages=128,sleep=.01)
    finally:src.close()
    end=db.execute('select max(received) from frames').fetchone()[0]
    entries=[s for s in sites() if s['region']==('Florida' if region=='florida' else 'Toronto')]
    axes=json.loads((root/'config/reconstruction/corridor-road-axes.json').read_text())
    full=build(db,entries,end,road_axes=axes,processing_interval_s=.5)
    # Fixed, nonoverlapping windows in the later half; no outcome-based selection.
    windows=[(2000,2010),(2400,2430),(2800,2860)]
    removed=[]
    for lo,hi in windows:
        n=db.execute('delete from frames where received>? and received<?',(full['start']+lo,full['start']+hi)).rowcount
        db.execute('delete from phase_samples where received>? and received<?',(full['start']+lo,full['start']+hi))
        removed.append(n)
    db.commit();masked=build(db,entries,end,road_axes=axes,processing_interval_s=.5);enhanced=build(db,entries,end,road_axes=axes,retain_stationary_context=True,processing_interval_s=.5);db.close()
    report=json.loads((root/'data/reconstruction/word-v1-collection/evaluation-001/report.json').read_text())
    model=json.loads((root/f'data/reconstruction/eight-hour-20261123/{region}/model.json').read_text())
    report['calibration']['parameters']=model['parameters']
    layers=generate(masked,report,same_class_recovery=True,endpoint_policy=model.get('endpoint_policy'),endpoint_excluded_sites=model.get('excluded_sites',[]))
    enhanced_layers=generate(enhanced,report,same_class_recovery=True,endpoint_policy=model.get('endpoint_policy'),endpoint_excluded_sites=model.get('excluded_sites',[]))
    rows=[]
    for (lo,hi),removed_count in zip(windows,removed):
        ground={};entirely_hidden=set()
        for site in full['sites']:
            for tr in site['tracks']:
                key=(site['id'],*tr.get('source_key',[])[:2]);p=np.asarray(tr['points'],float)
                if p[0,0]>lo and p[-1,0]<hi:entirely_hidden.add(key)
                if p[0,0]<=lo and p[-1,0]>=hi and np.all(np.diff(p[:,0])<=1.5):ground.setdefault(key,[]).append(tr)
        scores=[];unscorable=0;seen=set()
        enhanced_scores=[];enhanced_seen=set()
        for estimate in enhanced_layers['within_intersection']:
            p=np.asarray(estimate['points'],float)
            if p[0,0]>lo or p[-1,0]<hi:continue
            key=(estimate['site'],*estimate.get('identity_key',[]));truth=ground.get(key,[])
            if len(truth)!=1:continue
            tr=truth[0];actual=np.asarray(tr['points'],float);actual=actual[(actual[:,0]>lo)&(actual[:,0]<hi)]
            if len(actual)<3:continue
            sign=1 if tr['direction']=='eastbound' else -1
            p=p.copy();actual=actual.copy();p[:,1]*=sign;actual[:,1]*=sign
            enhanced_scores.append(metrics(p,actual,model['parameters']));enhanced_seen.add(key)
        for estimate in layers['within_intersection']:
            p=np.asarray(estimate['points'],float)
            if p[0,0]>lo or p[-1,0]<hi:continue
            key=(estimate['site'],*estimate.get('identity_key',[]));truth=ground.get(key,[])
            if len(truth)!=1:unscorable+=1;continue
            tr=truth[0];actual=np.asarray(tr['points'],float);actual=actual[(actual[:,0]>lo)&(actual[:,0]<hi)]
            if len(actual)<3:continue
            sign=1 if tr['direction']=='eastbound' else -1
            p=p.copy();actual=actual.copy();p[:,1]*=sign;actual[:,1]*=sign
            scores.append(metrics(p,actual,model['parameters']));seen.add(key)
        rows.append({'interval_s':[lo,hi],'duration_s':hi-lo,'removed_frames':removed_count,'continuous_endpoint_supported_ids':len(ground),
            'reconstructed_scored_ids':len(seen),'entirely_hidden_ids':len(entirely_hidden-set(ground)),
            'unscorable_estimates':unscorable,'quality':summarize(scores),'stationary_context_candidate':{'scored_ids':len(enhanced_seen),'quality':summarize(enhanced_scores)}})
    result={'region':region,'window':[full['start'],full['end']],'endpoint_context_version':full.get('endpoint_context_version'),
        'ingestion_epochs':full.get('ingestion_epochs',[]),'processing_interval_s':.5,'cases':rows,
        'limitations':['Whole-server outages simulated by deleting all frames and phase samples in fixed intervals.',
        'Only same-site continuity is scored; no ground truth between sensors.',
        'Entirely hidden vehicles have no recoverable endpoint evidence; no lines are fabricated.']}
    atomic(Path(output),result);print(json.dumps(result,indent=2),flush=True)
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--region',choices=['florida','finch'],required=True);p.add_argument('--output',required=True);a=p.parse_args();run(a.region,a.output)
