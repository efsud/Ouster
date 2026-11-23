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

def truth_candidates(full,lo,hi):
    from .spatial_bridges import endpoint
    ground={};hidden=set();short_context=set()
    for site in full['sites']:
        for tr in site['tracks']:
            if tr['class_type']!='2':continue
            key=(site['id'],*tr.get('source_key',[])[:2]);p=np.asarray(tr['points'],float)
            if p[0,0]>lo and p[-1,0]<hi:hidden.add(key)
            if not (p[0,0]<=lo and p[-1,0]>=hi and np.all(np.diff(p[:,0])<=1.5)):continue
            if endpoint(p[p[:,0]<=lo],True) is None or endpoint(p[p[:,0]>=hi],False) is None:
                short_context.add(key);continue
            ground.setdefault(key,[]).append(tr)
    return ground,hidden-set(ground),short_context-set(ground)

def run(region,output,windows=None,end=None):
    from dashboard.server import sites
    root=Path(__file__).resolve().parents[1]
    src=sqlite3.connect(f'file:{root}/data/{region}-rolling/buffer.sqlite3?mode=ro',uri=True,timeout=20)
    db=sqlite3.connect(':memory:')
    try:src.backup(db,pages=128,sleep=.01)
    finally:src.close()
    end=db.execute('select max(received) from frames').fetchone()[0] if end is None else end
    entries=[s for s in sites() if s['region']==('Florida' if region=='florida' else 'Toronto')]
    axes=json.loads((root/'config/reconstruction/corridor-road-axes.json').read_text())
    full=build(db,entries,end,road_axes=axes,processing_interval_s=.5)
    # Fixed, nonoverlapping windows in the later half; no outcome-based selection.
    windows=windows or [(2000,2010),(2400,2430),(2800,2860)]
    windows=sorted(windows)
    if any(not 0<=lo<hi<=3600 for lo,hi in windows) or any(a[1]>=b[0] for a,b in zip(windows,windows[1:])):
        raise ValueError('Outage masks must be disjoint and inside the one-hour window')
    removed=[]
    for lo,hi in windows:
        n=db.execute('delete from frames where received>? and received<?',(full['start']+lo,full['start']+hi)).rowcount
        db.execute('delete from phase_samples where received>? and received<?',(full['start']+lo,full['start']+hi))
        removed.append(n)
    db.commit();masked=build(db,entries,end,road_axes=axes,processing_interval_s=.5);enhanced=build(db,entries,end,road_axes=axes,retain_stationary_context=True,processing_interval_s=.5);db.close()
    report=json.loads((root/'data/reconstruction/word-v1-collection/evaluation-001/report.json').read_text())
    model=json.loads((root/f'data/reconstruction/eight-hour-20261123/{region}/model.json').read_text())
    report['calibration']['parameters']=model['parameters']
    policy={'parameters':model.get('endpoint_policy'),'excluded_sites':model.get('excluded_sites',[])}
    if region=='finch':
        from .reconstruction_layers import finch_endpoint_config
        override=root/'config/reconstruction/finch-endpoint-speed.json'
        policy=finch_endpoint_config(model,json.loads(override.read_text()) if override.exists() else None)
    layers=generate(masked,report,same_class_recovery=True,endpoint_policy=policy['parameters'],endpoint_excluded_sites=policy['excluded_sites'])
    enhanced_layers=generate(enhanced,report,same_class_recovery=True,endpoint_policy=policy['parameters'],endpoint_excluded_sites=policy['excluded_sites'])
    from .same_id_gaps import candidates
    audits={}
    for site in masked['sites']:
        audits[site['id']]=[]
        list(candidates(site,include_same_class=True,audit=audits[site['id']].append))
    rows=[]
    for (lo,hi),removed_count in zip(windows,removed):
        ground,entirely_hidden,short_context=truth_candidates(full,lo,hi)
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
        from collections import Counter
        reasons=Counter();unresolved=[]
        for key in set(ground)-seen:
            matches=[r for r in audits[key[0]] if tuple(r['identity'])==key[1:] and r['start']<=lo and r['end']>=hi]
            if not matches:reasons['missing_retained_endpoint_fragments']+=1
            else:
                reason=matches[0]['reason'];reasons['model_or_other_layer_gate' if reason=='candidate' else reason]+=1
            import hashlib
            detail={'identity_hash':hashlib.sha256(json.dumps(key).encode()).hexdigest(),'site':key[0],
                    'candidates':[{k:v for k,v in candidate.items() if k!='identity'} for candidate in matches]}
            if matches and matches[0]['reason']=='candidate':
                from .endpoint_speed import orient,reconstruct as diagnose
                candidate=matches[0];sign=1 if candidate['direction']=='eastbound' else -1
                correction=policy['parameters'] if key[0] not in policy['excluded_sites'] and 1.5<candidate['end']-candidate['start']<=90 else None
                check=diagnose(orient(candidate['start_endpoint'],sign),orient(candidate['end_endpoint'],sign),model['parameters'],correction)
                detail['solver_diagnostic']={k:check[k] for k in ('state','reason','violations','solver','endpoint_policy','endpoint_corrections','correction_rejection') if k in check}
            unresolved.append(detail)
        rows.append({'interval_s':[lo,hi],'duration_s':hi-lo,'removed_frames':removed_count,'continuous_endpoint_supported_ids':len(ground),
            'unresolved_endpoint_supported_reasons':dict(reasons),
            'unresolved_diagnostics':unresolved,
            'reconstructed_scored_ids':len(seen),'entirely_hidden_ids':len(entirely_hidden),'insufficient_visible_endpoint_context_ids':len(short_context),
            'unscorable_estimates':unscorable,'quality':summarize(scores),'stationary_context_candidate':{'scored_ids':len(enhanced_seen),'quality':summarize(enhanced_scores)}})
    result={'region':region,'window':[full['start'],full['end']],'endpoint_policy':policy,'transform_manifest':full.get('transform_manifest'),'endpoint_context_version':full.get('endpoint_context_version'),
        'ingestion_epochs':full.get('ingestion_epochs',[]),'processing_interval_s':.5,'cases':rows,
        'limitations':['Whole-server outages simulated by deleting all frames and phase samples in fixed intervals.',
        'Ground-truth denominator is recorded car fragments; unscorable estimates are reported separately.',
        'Only same-site continuity is scored; no ground truth between sensors.',
        'Entirely hidden vehicles have no recoverable endpoint evidence; no lines are fabricated.']}
    atomic(Path(output),result);print(json.dumps(result,indent=2),flush=True)
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--region',choices=['florida','finch'],required=True);p.add_argument('--output',required=True);p.add_argument('--long-gaps',action='store_true');p.add_argument('--end',type=float);a=p.parse_args()
    run(a.region,a.output,[(1900,1910),(2100,2130),(2350,2410),(2650,2740),(3000,3120)] if a.long_gaps else None,a.end)
