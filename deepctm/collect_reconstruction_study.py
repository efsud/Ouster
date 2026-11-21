"""Wait on existing Florida recording, audit fixed splits, then evaluate once.

Does not restart sensors or change retention. Saves reports, not raw archives.
"""
import argparse,json,sqlite3,time,tempfile,fcntl
from pathlib import Path
from .reconstruction_study import partition_track,masked_case,run
from .florida_rolling import build
ROOT=Path(__file__).resolve().parents[1]

def atomic(path,value):
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(value,indent=2,allow_nan=False));tmp.replace(path)

def readiness(snapshot,plan):
    result={k:{'tracks':0,'masks':{str(g):0 for g in plan['gap_seconds']},'sites':{}} for k in plan['spatial_partitions']}
    for site in snapshot['sites']:
        for tr in site['tracks']:
            split=partition_track(site['id'],tr,snapshot,plan)
            if split is None:continue
            r=result[split];r['tracks']+=1;r['sites'][site['id']]=r['sites'].get(site['id'],0)+1
            for gap in plan['gap_seconds']:
                if masked_case(tr,gap) is not None:r['masks'][str(gap)]+=1
    reasons=[]
    for split,r in result.items():
        if r['tracks']<30:reasons.append(split+': fewer than 30 complete car fragments')
        for gap in (5,10):
            if r['masks'][str(gap)]<10:reasons.append(f'{split}: fewer than 10 eligible {gap}s masks')
    return dict(ready=not reasons,partitions=result,reasons=reasons,thresholds={'tracks_per_partition':30,'masks_per_5s_and_10s':10,'longer_gaps':'reported where supported; not required for short-gap study'})

def main(folder):
    from dashboard.server import sites
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    lock=open(folder/'runner.lock','w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    plan=json.loads((ROOT/'config/reconstruction/florida-study.json').read_text());entries=[s for s in sites() if s['region']=='Florida']
    attempt=0
    while True:
        now=time.time();db=sqlite3.connect(f'file:{ROOT}/data/florida-rolling/buffer.sqlite3?mode=ro',uri=True,timeout=30)
        health={site:{'frames':n,'age_s':now-last if last else None} for site,n,last in db.execute('SELECT site,count(*),max(received) FROM frames GROUP BY site')}
        stale=[s['id'] for s in entries if s['id'] not in health or health[s['id']]['age_s']>120]
        if stale:
            db.close();atomic(folder/'status.json',dict(state='waiting_for_fresh_frames',updated_at=now,health=health,stale_sites=stale));time.sleep(30);continue
        snapshot=build(db,entries,now);db.close();audit=readiness(snapshot,plan)
        atomic(folder/'status.json',dict(state='collecting' if not audit['ready'] else 'evaluating',updated_at=time.time(),health=health,readiness=audit,window=[snapshot['start'],snapshot['end']]))
        print(json.dumps({'state':'ready' if audit['ready'] else 'collecting','counts':audit['partitions']}),flush=True)
        if audit['ready']:
            attempt+=1;output=folder/f'evaluation-{attempt:03}'
            while output.exists():attempt+=1;output=folder/f'evaluation-{attempt:03}'
            with tempfile.TemporaryDirectory(prefix='florida-reconstruction-') as temp:
                source=Path(temp)/'snapshot.json';source.write_text(json.dumps(snapshot));report=run(source,output)
            if report['state']=='evaluated_ablation':
                atomic(folder/'status.json',dict(state='evaluated_ablation',updated_at=time.time(),report=str(output/'report.json'),readiness=audit,selected_method=report['selected_method'],test=report['test'],uncertainty=report['uncertainty']))
                print('Study complete: '+str(output/'report.json'),flush=True);return
            atomic(folder/'status.json',dict(state='collecting_more',updated_at=time.time(),last_result=report['state'],report=str(output/'report.json'),readiness=audit))
        time.sleep(60)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',default='data/reconstruction/word-v1-collection');a=p.parse_args();main(a.output)
