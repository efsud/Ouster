"""Unpublished fallback-solver comparison on identity-separated local masks."""
import argparse,json,time,hashlib
from pathlib import Path
from .archive_extension import cases
from .corridor_campaign import subset,earlier_ids,atomic,identity
from .trajectory_reconstruction import baseline,refine
from .quadratic_refinement import solve
from .reconstruction_study import metrics,summarize

def evaluate(snapshot,params,deadline):
    rows=cases(snapshot,'test',5);records=[]
    for rank,site,tr,gap,(a,b,truth) in rows:
        if time.time()>=deadline:break
        old=refine(a,b,baseline(a,b),**params,smoothness=.01,position_tolerance=0,speed_tolerance=0)
        estimates={'baseline':old}
        if old['state']=='candidate':estimates.update(uniform=old,adaptive=old)
        else:
            uniform=solve(a,b,params);estimates['uniform']=uniform
            estimates['adaptive']=uniform if uniform['state']=='candidate' else solve(a,b,params,adaptive=True)
        row={'identity_hash':hashlib.sha256(identity(site,tr).encode()).hexdigest(),'site':site['id'],'gap_s':gap,'states':{},'metrics':{}}
        for method,r in estimates.items():
            row['states'][method]=r['state']
            if r['state']=='candidate':row['metrics'][method]=metrics(r['points'],truth,params)
        records.append(row)
    totals={}
    for method in ('baseline','uniform','adaptive'):
        accepted=[r for r in records if method in r['metrics']];new=[r for r in accepted if 'baseline' not in r['metrics']]
        totals[method]={'accepted':len(accepted),'quality':summarize([r['metrics'][method] for r in accepted]),
            'added':len(new),'distinct_added_ids':len({r['identity_hash'] for r in new}),
            'added_quality':summarize([r['metrics'][method] for r in new])}
    return {'state':'complete' if time.time()<deadline else 'deadline_reached','eligible':len(rows),
            'evaluated':len(records),'methods':totals,'cases':records}

def run(region,output,deadline):
    root=Path(__file__).resolve().parents[1];raw=(root/f'data/{region}-rolling/snapshot.json').read_bytes();s=json.loads(raw)
    params=json.loads((root/f'data/reconstruction/eight-hour-20261123/{region}/model.json').read_text())['parameters']
    test=subset(s,2730,3600,earlier_ids(s,2700));r=evaluate(test,params,deadline)
    r.update(region=region,window=[s['start'],s['end']],parameters=params,transform_manifest=s.get('transform_manifest'),
        snapshot_sha256=hashlib.sha256(raw).hexdigest(),limitations=['Development comparison; no automatic deployment.',
        'No physical bound or endpoint constraint relaxed; existing accepted paths preserved.',
        'Local temporal masks, correlated gap lengths, no intersensor identity ground truth.'])
    atomic(Path(output),r);print(region,r['methods'],flush=True);return r

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--region',choices=['florida','finch'],required=True);p.add_argument('--output',required=True);p.add_argument('--deadline',type=float,required=True)
    a=p.parse_args();run(a.region,a.output,a.deadline)
