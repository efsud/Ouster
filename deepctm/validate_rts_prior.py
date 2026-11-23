"""Chronological, identity-separated RTS-prior ablation on recorded trajectories."""
import argparse,json,time,hashlib
from pathlib import Path
import numpy as np
from .archive_extension import cases
from .corridor_campaign import subset,earlier_ids,atomic
from .endpoint_speed import reconstruct
from .rts_prior import estimate
from .reconstruction_study import metrics,summarize

def visible(tr,a,b):
    p=np.asarray(tr['points'],float).copy();sign=1 if tr['direction']=='eastbound' else -1;p[:,1]*=sign
    before=p[(p[:,0]<=a['t']+1e-8)&(p[:,0]>=a['t']-3)]
    after=p[(p[:,0]>=b['t']-1e-8)&(p[:,0]<=b['t']+3)]
    return before,after

def noise(training):
    errors=[]
    for site in training['sites']:
        for tr in site['tracks']:
            p=np.asarray(tr['points'],float)
            for i in range(1,len(p)-1):
                a,c=p[i-1],p[i+1];b=p[i]
                if c[0]-a[0]>1.5 or max(a[2],b[2],c[2])>.2:continue
                if max(a[1],b[1],c[1])-min(a[1],b[1],c[1])>.2:continue
                u=(b[0]-a[0])/(c[0]-a[0]);res=b[1]-(a[1]*(1-u)+c[1]*u)
                errors.append(res/np.sqrt(1+(1-u)**2+u*u))
    if len(errors)<30:return .04,{'samples':len(errors),'source':'declared 0.2 m standard-deviation fallback; not sensor accuracy'}
    e=np.asarray(errors);sigma=1.4826*np.median(abs(e-np.median(e)))
    return float(np.clip(sigma*sigma,.0001,1)),{'samples':len(errors),'source':'training stationary-position residuals; detector-noise-sensitive proxy'}

def evaluate(rows,params,variance,methods,deadline):
    scores={m:{} for m in methods};details=[]
    for i,(rank,site,tr,gap,(a,b,truth)) in enumerate(rows):
        if time.time()>deadline:break
        before,after=visible(tr,a,b)
        if len(before)<5 or len(after)<5:continue
        entry={'identity_hash':hashlib.sha256(json.dumps([site['id'],tr['source_key'][:2]]).encode()).hexdigest(),'site':site['id'],'gap_s':gap,'metrics':{}}
        for method in methods:
            if method=='baseline':r=reconstruct(a,b,params,None)
            else:r=estimate(before,after,a,b,params,q=float(method),measurement_variance=variance)
            if r['state']=='candidate':scores[method][i]=metrics(r['points'],truth,params);entry['metrics'][method]=scores[method][i]
        details.append(entry)
    common=set.intersection(*(set(s) for s in scores.values())) if scores else set()
    result={m:{'eligible':len(rows),'evaluated':len(details),'accepted':len(sc),'all':summarize(list(sc.values())),
        'common':summarize([sc[i] for i in common]),'by_gap':{str(g):summarize([sc[i] for i in common if rows[i][3]==g]) for g in (10,30,60,90)}} for m,sc in scores.items()}
    return {'summary':result,'cases':details}

def run(region,output,deadline):
    root=Path(__file__).resolve().parents[1];raw=(root/f'data/{region}-rolling/snapshot.json').read_bytes();s=json.loads(raw)
    params=json.loads((root/f'data/reconstruction/eight-hour-20261123/{region}/model.json').read_text())['parameters']
    training=subset(s,0,1410);variance,evidence=noise(training)
    validation=subset(s,1470,2490,earlier_ids(s,1440));test=subset(s,2550,3600,earlier_ids(s,2520))
    val=cases(validation,'test',5);heldout=cases(test,'test',5)
    report={'region':region,'window':[s['start'],s['end']],'snapshot_sha256':hashlib.sha256(raw).hexdigest(),'parameters':params,
        'measurement_variance_m2':variance,'noise_evidence':evidence,'split':'first 40% noise estimate; next 30% method selection; final 30% test; 30 s embargo; whole fragments and earlier IDs excluded',
        'limitations':['Retrospective local masks only; no cross-sensor identities verified.','Correlated masks; no field-calibrated uncertainty.','No signal or leader information used.'],'state':'validation'}
    report['validation']=evaluate(val,params,variance,['baseline','0.001','0.01','0.1','1.0'],deadline)
    base=report['validation']['summary']['baseline'];choices=['baseline']
    if base['common'].get('n',0)>=10:
        for method,row in report['validation']['summary'].items():
            if method=='baseline' or row['accepted']<base['accepted']:continue
            if row['common']['speed_mae_mps']<=base['common']['speed_mae_mps']*1.05 and row['common']['p95_case_mae_m']<=base['common']['p95_case_mae_m']*1.05:choices.append(method)
    selected=min(choices,key=lambda m:report['validation']['summary'][m]['common'].get('mae_m',float('inf')))
    report.update(state='selection_frozen',selected=selected,frozen_at=time.time());atomic(Path(output),report)
    report['test']=evaluate(heldout,params,variance,list(dict.fromkeys(['baseline',selected])),deadline);report['state']='complete' if time.time()<deadline else 'deadline_reached';atomic(Path(output),report)
    print(region,'selected',selected,'validation',{m:r['common'] for m,r in report['validation']['summary'].items()},'test',report['test']['summary'],flush=True)
    return report
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--region',choices=['florida','finch'],required=True);p.add_argument('--output',required=True);p.add_argument('--deadline',type=float,required=True);a=p.parse_args();run(a.region,a.output,a.deadline)

def prospective(snapshot,params,protocol,deadline):
    """Frozen hybrid on future IDs; baseline availability is preserved exactly."""
    rows=cases(snapshot,'test',3);records=[]
    for rank,site,tr,gap,(a,b,truth) in rows:
        if time.time()>=deadline:break
        base=reconstruct(a,b,params,None);entry={'identity_hash':hashlib.sha256(json.dumps([site['id'],tr['source_key'][:2]]).encode()).hexdigest(),'site':site['id'],'gap_s':gap,'accepted':base['state']=='candidate','rts_used':False}
        if base['state']=='candidate':
            before,after=visible(tr,a,b);candidate=None
            if len(before)>=5 and len(after)>=5:candidate=estimate(before,after,a,b,params,protocol['q'],protocol['measurement_variance_m2'])
            entry['baseline']=metrics(base['points'],truth,params)
            entry['rts_used']=candidate is not None and candidate['state']=='candidate'
            entry['hybrid']=metrics(candidate['points'],truth,params) if entry['rts_used'] else entry['baseline']
        records.append(entry)
    return {'state':'complete' if time.time()<deadline else 'deadline_reached','cases':records,
        'summary':{m:summarize([r[m] for r in records if r['accepted']]) for m in ('baseline','hybrid')},
        'eligible':len(rows),'evaluated':len(records),'rts_used':sum(r['rts_used'] for r in records),'q':protocol['q'],'measurement_variance_m2':protocol['measurement_variance_m2']}
