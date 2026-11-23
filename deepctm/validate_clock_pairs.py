"""Paired masking of identical physical observations under two time bases.

SDK elapsed time is receipt-anchored per session; no absolute timezone or
cross-sensor synchronization claim follows from this within-sensor experiment.
"""
import argparse,json,sqlite3,time
from pathlib import Path
import numpy as np
from .florida_rolling import build
from .archive_extension import cases
from .spatial_bridges import endpoint
from .trajectory_reconstruction import baseline,refine
from .reconstruction_study import metrics,summarize

def run(region,report,limit=5):
    from dashboard.server import sites
    root=Path(__file__).resolve().parents[1];source=sqlite3.connect(f'file:{root}/data/{region}-rolling/buffer.sqlite3?mode=ro',uri=True)
    memory=sqlite3.connect(':memory:');source.backup(memory,pages=128,sleep=.01);source.close()
    observed={}
    def observe(site,key,points):observed[site['id'],tuple(key),round(points[0][0],2)]=points
    axes=json.loads((root/'config/reconstruction/corridor-road-axes.json').read_text());name='Florida' if region=='florida' else 'Toronto'
    s=build(memory,[x for x in sites() if x['region']==name],time.time(),track_observer=observe,road_axes=axes,time_basis='sensor_elapsed');memory.close()
    params=report['calibration']['parameters'];records=[]
    for rank,site,tr,gap,(a,b,truth) in cases(s,'test',limit):
        raw=observed[site['id'],tuple(tr['source_key']),round(tr['receipt_start'],2)]
        p=np.asarray(tr['points'],float);sign=1 if tr['direction']=='eastbound' else -1;p[:,1]*=sign
        i=int(np.where(p[:,0]==a['t'])[0][0]);j=int(np.where(p[:,0]==b['t'])[0][0])
        receipt=p.copy();receipt[:,0]=[point[5]-s['start'] for point in raw]
        aa=endpoint(receipt[:i+1],True);bb=endpoint(receipt[j:],False)
        row={'rank':rank,'site':site['id'],'gap_s':gap,'states':{},'metrics':{},'receipt_gap_s':float(receipt[j,0]-receipt[i,0])}
        for method,left,right,target in [('receipt',aa,bb,receipt[i+1:j]),('sensor_elapsed',a,b,truth)]:
            if left is None or right is None:
                row['states'][method]='visible_endpoint_context_unavailable';continue
            if not 0<right['t']-left['t']<=120:
                row['states'][method]='duration_bound';continue
            result=refine(left,right,baseline(left,right),**params,smoothness=.01,position_tolerance=0,speed_tolerance=0)
            row['states'][method]=result['state']
            if result['state']=='candidate':row['metrics'][method]=metrics(result['points'],target,params)
        records.append(row)
    common=[r for r in records if len(r['metrics'])==2]
    summaries={m:{'accepted':sum(m in r['metrics'] for r in records),'quality':summarize([r['metrics'][m] for r in records if m in r['metrics']]),
                  'common':summarize([r['metrics'][m] for r in common])} for m in ('receipt','sensor_elapsed')}
    return {'created_at':time.time(),'window':[s['start'],s['end']],'eligible':len(records),'parameters':params,'summary':summaries,'cases':records,
            'limitations':['Exactly the same physical observations are hidden in both time bases.','Cases selected from continuous sensor-time tracks; availability comparisons are conditional on that selection.','No absolute timezone or cross-sensor synchronization is verified.','Same fixed physics; no parameter fitting.','Several gap lengths can reuse one vehicle.']}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--region',choices=['florida','finch'],required=True);p.add_argument('--report',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    r=run(a.region,json.loads(Path(a.report).read_text()));Path(a.output).parent.mkdir(parents=True,exist_ok=True);Path(a.output).write_text(json.dumps(r,indent=2));print({k:v for k,v in r.items() if k!='cases'})
