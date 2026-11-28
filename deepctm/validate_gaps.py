"""Hide complete interior intervals, then score only withheld observations.
No fitting or selection on this evaluation. Never join identities or intersections.
"""
import argparse,json,sqlite3,time
from pathlib import Path
import numpy as np
from .local_gaps import bridge,VEHICLES
from .florida_rolling import build

def evaluate_track(points,duration):
    # Require continuous ground truth and five visible samples at either end.
    if len(points)<12 or any(not 0<b[0]-a[0]<=1.5 for a,b in zip(points,points[1:])):return None
    times=np.array([p[0] for p in points]);left=(times[0]+times[-1]-duration)/2
    i=int(np.searchsorted(times,left));j=int(np.searchsorted(times,times[i]+duration,side='right'))-1 if i<len(times) else len(times)
    if i<4 or j+4>=len(points) or j-i<2 or not duration-1.5<=times[j]-times[i]<=30:return None
    before=points[i-4:i+1];after=points[j:j+5];truth=points[i+1:j]
    estimated=bridge(before,after)
    t=np.array([p[0] for p in truth]);actual=np.array([p[1] for p in truth]);speed=np.array([p[3] for p in truth])
    a,b=points[i],points[j];v=(b[1]-a[1])/(b[0]-a[0]);linear=a[1]+v*(t-a[0])
    result={'duration':float(b[0]-a[0]),'accepted':estimated is not None,'n':len(t),'linear_mae_m':float(np.mean(abs(linear-actual))),'moving_gap':bool(np.ptp(actual)>5)}
    if estimated is not None:
        est=np.array(estimated);pred=np.interp(t,est[:,0],est[:,1]);vs=np.interp(t,est[:,0],est[:,2]);err=pred-actual
        result.update(mae_m=float(np.mean(abs(err))),rmse_m=float(np.sqrt(np.mean(err**2))),max_error_m=float(np.max(abs(err))),speed_mae_m_s=float(np.mean(abs(vs-speed))))
        result['example']={'seconds':(t-a[0]).tolist(),'actual_m':actual.tolist(),'estimated_m':pred.tolist(),'linear_m':linear.tolist()}
    return result

def run(output,reuse_window=False):
    previous=json.loads(Path(output,'gap-validation.json').read_text()) if reuse_window else None
    from dashboard.server import sites
    report={'created_at':time.time(),'method':'Fixed 5/10/20/30-second centered masks; five visible samples on each side; withheld interior never enters bridge',
      'limitations':['Retrospective interpolation uses observations after the gap; not a causal forecast.','One mask per track per duration; cases across durations are correlated.','Local aligned longitudinal positions only; no cross-sensor or intermediate-road validation.','Speed reference uses sensor time while interpolation uses receipt time.','Accepted-only errors must be read with acceptance rate; rejected cases are not filled.'],'regions':{}}
    for region,folder in [('Florida','florida'),('Toronto','finch')]:
        rows=[]
        def observer(site,key,points):
            if key[2] not in VEHICLES:return
            for duration in [5,10,20,30]:
                result=evaluate_track(points,duration)
                if result is not None:rows.append(dict(result,site=site['id'],requested_seconds=duration))
        db=sqlite3.connect(f'file:data/{folder}-rolling/buffer.sqlite3?mode=ro',uri=True)
        end=previous['regions'][region]['source_end'] if previous else db.execute('SELECT MAX(received) FROM frames').fetchone()[0]
        if end:build(db,[s for s in sites() if s['region']==region],end,observer)
        db.close();groups=[]
        for site in sorted({r['site'] for r in rows}):
            for duration in [5,10,20,30]:
                cases=[r for r in rows if r['site']==site and r['requested_seconds']==duration];accepted=[r for r in cases if r['accepted']]
                groups.append({'site':site,'requested_seconds':duration,'eligible':len(cases),'accepted':len(accepted),
                    'moving_accepted':sum(r['moving_gap'] for r in accepted),
                    'moving_mae_m':float(np.mean([r['mae_m'] for r in accepted if r['moving_gap']])) if any(r['moving_gap'] for r in accepted) else None,
                    'p95_case_mae_m':float(np.quantile([r['mae_m'] for r in accepted],.95)) if accepted else None,
                    'worst_case_mae_m':max((r['mae_m'] for r in accepted),default=None),
                    **{k:float(np.mean([r[k] for r in accepted])) if accepted else None for k in ['mae_m','rmse_m','max_error_m','speed_mae_m_s','linear_mae_m']}})
        # Save derived scores and a few worked examples, not a copy of raw frames.
        examples=[r for r in rows if r['accepted']];examples=sorted(examples,key=lambda r:r['mae_m'])
        report['regions'][region]={'source_end':end,'groups':groups,'examples':[examples[i] for i in sorted({0,len(examples)//2,len(examples)-1})] if examples else []}
    Path(output).mkdir(parents=True,exist_ok=True);Path(output,'gap-validation.json').write_text(json.dumps(report,indent=2));return report
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--reuse-window',action='store_true');a=p.parse_args();run(a.output,a.reuse_window)
