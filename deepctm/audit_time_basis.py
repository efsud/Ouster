"""Read-only coverage audit of receipt and experimental SDK-elapsed timelines."""
import argparse,json,sqlite3,time
from pathlib import Path
import numpy as np
from .florida_rolling import build
from .corridor_campaign import atomic

def run(region,output):
    from dashboard.server import sites
    root=Path(__file__).resolve().parents[1]
    source=sqlite3.connect(f'file:{root}/data/{region}-rolling/buffer.sqlite3?mode=ro',uri=True,timeout=20)
    memory=sqlite3.connect(':memory:')
    try:source.backup(memory,pages=128,sleep=.01)
    finally:source.close()
    end=memory.execute('select max(received) from frames').fetchone()[0]
    entries=[s for s in sites() if s['region']==('Florida' if region=='florida' else 'Toronto')]
    axes=json.loads((root/'config/reconstruction/corridor-road-axes.json').read_text());methods={}
    for method,basis,reorder in [('receipt','receipt',0),('sensor_strict','sensor_elapsed',0),('sensor_bounded_order','sensor_elapsed',.25)]:
        snapshot=build(memory,entries,end,road_axes=axes,time_basis=basis,processing_interval_s=.5,clock_reorder_s=reorder)
        rows=[]
        for site in snapshot['sites']:
            tracks=[tr for tr in site['tracks'] if tr['class_type']=='2'];seconds=0.
            for tr in tracks:
                dt=np.diff(np.asarray(tr['points'],float)[:,0]);seconds+=float(dt[(dt>0)&(dt<=1.5)].sum())
            rows.append({'site':site['id'],'name':site['name'],'raw_frames':site['raw_frames'],
                'plotted_frames':site['frames'],'car_fragments':len(tracks),
                'distinct_car_ids':len({tuple(tr['source_key'][:2]) for tr in tracks}),
                'observed_car_seconds':seconds,'fragment_breaks':site['fragment_break_reasons'],
                'clock_audit':site['clock_audit']})
        methods[method]=rows
    memory.close();result={'region':region,'created_at':time.time(),'window':[end-3600,end],
        'transform_manifest':snapshot['transform_manifest'],'methods':methods,
        'limitations':['Diagnostic only; source receipts and timestamps remain untouched.',
        'Observed car-seconds are exposure across vehicles, not road coverage or recovered missing data.',
        'Different timelines select different actual frames at 0.5-second cadence.',
        'Bounded ordering allows <=0.25 s lateness on <=1% of frames; duplicate timestamps or larger resets reject the experimental session.',
        'No absolute timezone or intersensor synchronization verified; no production change.']}
    atomic(Path(output),result)
    for method,rows in methods.items():print(region,method,sum(r['car_fragments'] for r in rows),round(sum(r['observed_car_seconds'] for r in rows)),flush=True)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--region',choices=['florida','finch'],required=True);p.add_argument('--output',required=True);a=p.parse_args();run(a.region,a.output)
