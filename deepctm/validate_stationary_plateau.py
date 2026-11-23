"""Recorded local masks for the narrow stationary measurement-noise hypothesis."""
import argparse,json,time,hashlib
from pathlib import Path
from .archive_extension import cases
from .corridor_campaign import subset,earlier_ids,atomic,identity,POLICY
from .endpoint_speed import reconstruct
from .stationary_plateau import estimate
from .reconstruction_study import metrics,summarize

def evaluate(snapshot,params,deadline):
    rows=[r for r in cases(snapshot,'test',8) if r[3]<=30];records=[]
    for rank,site,tr,gap,(a,b,truth) in rows:
        if time.time()>=deadline:break
        base=reconstruct(a,b,params,POLICY);r=base if base['state']=='candidate' else estimate(a,b,same_identity=True)
        row={'site':site['id'],'identity_hash':hashlib.sha256(identity(site,tr).encode()).hexdigest(),
             'gap_s':gap,'accepted':r['state']=='candidate','added':r['state']=='candidate' and base['state']!='candidate'}
        if row['accepted']:row['metrics']=metrics(r['points'],truth,params)
        records.append(row)
    added=[r for r in records if r['added']]
    return {'state':'complete' if time.time()<deadline else 'deadline_reached','eligible':len(rows),'evaluated':len(records),
        'added':len(added),'distinct_added_ids':len({r['identity_hash'] for r in added}),
        'added_quality':summarize([r['metrics'] for r in added]),'cases':records}

def run(region,output,deadline):
    root=Path(__file__).resolve().parents[1];raw=(root/f'data/{region}-rolling/snapshot.json').read_bytes();s=json.loads(raw)
    params=json.loads((root/f'data/reconstruction/eight-hour-20261123/{region}/model.json').read_text())['parameters']
    r=evaluate(subset(s,2730,3600,earlier_ids(s,2700)),params,deadline)
    r.update(region=region,window=[s['start'],s['end']],snapshot_sha256=hashlib.sha256(raw).hexdigest(),
        limitations=['Development diagnostic only.','Same-ID latent stationary position, not exact interpolation.',
        'Raw observations unchanged; endpoint residual <=0.05 m.','No cross-sensor identity inference.'])
    atomic(Path(output),r);print(region,{k:v for k,v in r.items() if k!='cases'},flush=True);return r

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--region',choices=['florida','finch'],required=True);p.add_argument('--output',required=True);p.add_argument('--deadline',type=float,required=True)
    a=p.parse_args();run(a.region,a.output,a.deadline)
