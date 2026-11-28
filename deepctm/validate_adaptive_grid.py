"""Recorded-mask audit of a finer endpoint grid; never auto-publishes paths."""
import argparse,json,time,hashlib
from pathlib import Path
from .archive_extension import cases
from .corridor_campaign import subset,earlier_ids,atomic,identity
from .adaptive_endpoint_grid import retry
from .reconstruction_study import metrics,summarize

def evaluate(snapshot,params,deadline):
    rows=cases(snapshot,'test',5);records=[]
    for rank,site,tr,gap,(a,b,truth) in rows:
        if time.time()>=deadline:break
        estimate,added=retry(a,b,params)
        entry={'identity_hash':hashlib.sha256(identity(site,tr).encode()).hexdigest(),
               'site':site['id'],'gap_s':gap,'accepted':estimate['state']=='candidate','added':added}
        if entry['accepted']:entry['metrics']=metrics(estimate['points'],truth,params)
        else:entry['reason']=estimate.get('reason')
        records.append(entry)
    added=[r for r in records if r['added']]
    return {'state':'complete' if time.time()<deadline else 'deadline_reached','eligible':len(rows),
            'evaluated':len(records),'accepted':sum(r['accepted'] for r in records),
            'added':len(added),'distinct_added_ids':len({r['identity_hash'] for r in added}),
            'added_quality':summarize([r['metrics'] for r in added]),'cases':records}

def run(region,output,deadline):
    root=Path(__file__).resolve().parents[1];raw=(root/f'data/{region}-rolling/snapshot.json').read_bytes();s=json.loads(raw)
    params=json.loads((root/f'data/reconstruction/eight-hour-20261123/{region}/model.json').read_text())['parameters']
    test=subset(s,2730,3600,earlier_ids(s,2700))
    result=evaluate(test,params,deadline)
    result.update(region=region,window=[s['start'],s['end']],parameters=params,
        transform_manifest=s.get('transform_manifest'),snapshot_sha256=hashlib.sha256(raw).hexdigest(),
        limitations=['Development diagnostic; requires later prospective validation.',
                      'Car local temporal masks only; no intersensor identity truth.',
                      'Same physical bounds; existing accepted solutions remain unchanged.',
                      'Several gap lengths may reuse a vehicle.'])
    atomic(Path(output),result);print({k:v for k,v in result.items() if k not in ('cases','transform_manifest')},flush=True)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--region',choices=['florida','finch'],required=True);p.add_argument('--output',required=True);p.add_argument('--deadline',type=float,required=True)
    a=p.parse_args();run(a.region,a.output,a.deadline)
