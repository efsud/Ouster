"""Spatial-and-temporal holdout study for the supplied Word recommendations.

M1 and the kinematic-only M4 ablation are scored now. M2/M3/full M4 are not
silently approximated when lane, leader and CTM/signal evidence is unavailable.
"""
import argparse,hashlib,json,math,time
from pathlib import Path
import numpy as np
from .spatial_bridges import endpoint
from .trajectory_reconstruction import baseline,refine


def partition_track(site,track,snapshot,plan):
    if track.get('class_type')!='2' or track.get('method'):return None
    points=track.get('points',[])
    if len(points)<12:return None
    duration=snapshot['end']-snapshot['start'];pad=plan['boundary_embargo_seconds']
    for split,sites in plan['spatial_partitions'].items():
        lo,hi=plan['time_fractions'][split]
        if site in sites and points[0][0]>=lo*duration+pad and points[-1][0]<=hi*duration-pad:return split
    return None


def masked_case(track,seconds):
    p=np.asarray(track['points'],float)
    if np.any(np.diff(p[:,0])<=0) or np.any(np.diff(p[:,0])>1.5):return None
    sign=1 if track['direction']=='eastbound' else -1;p=p.copy();p[:,1]*=sign
    left=(p[0,0]+p[-1,0]-seconds)/2;i=np.searchsorted(p[:,0],left)
    if i>=len(p):return None
    j=np.searchsorted(p[:,0],p[i,0]+seconds,side='right')-1
    if i<4 or j+4>=len(p) or j-i<3:return None
    a=endpoint(p[i-4:i+1],True);b=endpoint(p[j:j+5],False)
    if a is None or b is None or min(a['v'],b['v'])<-.5 or b['x']<a['x']:return None
    return a,b,p[i+1:j]


def metrics(pred,truth,parameters):
    x=np.interp(truth[:,0],pred[:,0],pred[:,1]);v=np.interp(truth[:,0],pred[:,0],pred[:,2]);err=x-truth[:,1]
    dt=np.diff(truth[:,0],prepend=truth[0,0]);actual_stop=truth[:,2]<.5;pred_stop=v<.5;acc=np.diff(pred[:,2])/np.diff(pred[:,0])
    return dict(mae_m=float(np.mean(abs(err))),rmse_m=float(np.sqrt(np.mean(err**2))),speed_mae_mps=float(np.mean(abs(v-truth[:,2]))),max_error_m=float(np.max(abs(err))),
      stop_time_error_s=float(abs(np.sum(dt*actual_stop)-np.sum(dt*pred_stop))),actual_stop=bool(np.sum(dt*actual_stop)>=2),predicted_stop=bool(np.sum(dt*pred_stop)>=2),
      moving=bool(np.ptp(truth[:,1])>5),physics_violation=bool(np.any(pred[:,2]<-1e-5) or np.any(pred[:,2]>parameters['vmax']+1e-5) or np.any(acc<parameters['amin']-1e-5) or np.any(acc>parameters['amax']+1e-5)))


def summarize(rows):
    if not rows:return {'n':0}
    tp=sum(r['actual_stop'] and r['predicted_stop'] for r in rows);pred=sum(r['predicted_stop'] for r in rows);actual=sum(r['actual_stop'] for r in rows)
    return dict(n=len(rows),**{k:float(np.mean([r[k] for r in rows])) for k in ['mae_m','rmse_m','speed_mae_mps','stop_time_error_s','physics_violation']},
      p95_case_mae_m=float(np.quantile([r['mae_m'] for r in rows],.95)),stop_precision=tp/pred if pred else None,stop_recall=tp/actual if actual else None)


def run(source,output,config='config/reconstruction/florida-study.json'):
    raw=Path(source).read_bytes();s=json.loads(raw);plan=json.loads(Path(config).read_text());output=Path(output);output.mkdir(parents=True,exist_ok=False)
    splits={k:[] for k in plan['spatial_partitions']};counts={k:{} for k in splits};all_keys={k:set() for k in splits}
    # Explicitly prevent a same-site session/object/class key from spanning splits.
    for site in s['sites']:
        for tr in site['tracks']:
            split=partition_track(site['id'],tr,s,plan)
            if split:
                key=(site['id'],*tr.get('source_key',[]));all_keys[split].add(key);splits[split].append((site['id'],tr));counts[split][site['id']]=counts[split].get(site['id'],0)+1
    assert not(all_keys['train']&all_keys['validation'] or all_keys['train']&all_keys['test'] or all_keys['validation']&all_keys['test'])
    speeds=[];accelerations=[]
    for site,tr in splits['train']:
        p=np.asarray(tr['points']);v=p[:,2];dt=np.diff(p[:,0]);valid=(dt>0)&(dt<=1.5)
        speeds.extend(v[v>=0]);accelerations.extend((np.diff(v)[valid]/dt[valid]).tolist())
    report=dict(state='input_audit',source_sha256=hashlib.sha256(raw).hexdigest(),source_window=[s['start'],s['end']],created_at=time.time(),plan=plan,track_counts=counts,
      unavailable_methods={'M2':'No supported same-lane leader metadata in rolling track schema','M3':'No calibrated per-cell queue field with verified movement permissions','M4_full':'M2/M3 priors unavailable; only kinematic ablation evaluated'},limitations=plan['limitations']+['Masks at several lengths reuse tracks; not independent samples','Endpoint travel time is given, so travel-time agreement would be tautological','No ground truth between actual sensors; local masking cannot verify cross-sensor identities'])
    def save(): (output/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False))
    if len(speeds)<100 or len(accelerations)<100:report['state']='insufficient_training_data';save();return report
    # Empirical robust limits with declared broad numerical guardrails; never test fit.
    params=dict(vmax=float(np.clip(np.quantile(speeds,.995),5,35)),amin=float(np.clip(np.quantile(accelerations,.01),-6,-1)),amax=float(np.clip(np.quantile(accelerations,.99),1,4)))
    report['calibration']=dict(parameters=params,speed_samples=len(speeds),acceleration_samples=len(accelerations),source='training partition only; detector-noise-sensitive empirical limits')
    methods=['M1_linear','M1_hermite']+[f'kinematic_{v}' for v in plan['optimization_smoothness_candidates']]
    cases={};evaluations={}
    for split in ('validation','test'):
        cases[split]=[]
        for site,tr in splits[split]:
            for gap in plan['gap_seconds']:
                masked=masked_case(tr,gap)
                if masked is not None:cases[split].append((site,tr,gap,masked))
    def evaluate(split,choices):
        results={m:{} for m in choices}
        for cid,(site,tr,gap,(a,b,truth)) in enumerate(cases[split]):
            for method in choices:
                pred=baseline(a,b,'linear' if method=='M1_linear' else 'hermite')
                if method.startswith('kinematic_'):
                    result=refine(a,b,pred,**params,smoothness=float(method.split('_')[1]))
                    if result['state']!='candidate':continue
                    pred=result['points']
                results[method][cid]=dict(metrics(pred,truth,params),site=site,gap_seconds=gap)
        return results
    validation=evaluate('validation',methods);common=set.intersection(*(set(v) for v in validation.values()))
    report['validation']={m:{'eligible':len(cases['validation']),'accepted':len(rows),'common':summarize([rows[i] for i in common])} for m,rows in validation.items()}
    if len(common)<10:report['state']='insufficient_validation_cases';save();return report
    winner=min(methods,key=lambda m:(report['validation'][m]['common']['mae_m'],methods.index(m)))
    # Freeze selection before any test inference/scoring. Baselines remain comparisons.
    report['selected_method']=winner;report['state']='selection_frozen';save()
    test=evaluate('test',list(dict.fromkeys(['M1_linear','M1_hermite',winner])));common_test=set.intersection(*(set(v) for v in test.values()))
    report['test']={m:{'eligible':len(cases['test']),'accepted':len(rows),'common':summarize([rows[i] for i in common_test]),
      'by_gap_and_regime':{f'{g}s_{regime}':summarize([rows[i] for i in common_test if rows[i]['gap_seconds']==g and rows[i]['moving']==moving]) for g in plan['gap_seconds'] for regime,moving in [('moving',True),('stationary',False)]}} for m,rows in test.items()}
    errors=sorted(r['max_error_m'] for r in validation[winner].values());q=errors[min(len(errors)-1,math.ceil((len(errors)+1)*.9)-1)]
    accepted=list(test[winner].values());report['uncertainty']={'nominal':.9,'radius_m':q,'calibrated_on':'validation max point error per mask','test_full_gap_coverage':sum(r['max_error_m']<=q for r in accepted)/len(accepted) if accepted else None,'warning':'Correlated masks and spatial domain shift; empirical coverage only, not guaranteed calibrated probability'}
    report['state']='evaluated_ablation' if common_test else 'insufficient_test_cases';save();return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--snapshot',required=True);p.add_argument('--output',required=True);a=p.parse_args();r=run(a.snapshot,a.output);print(json.dumps({k:r[k] for k in ['state','track_counts','selected_method','test','uncertainty'] if k in r},indent=2))
