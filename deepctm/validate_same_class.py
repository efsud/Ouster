"""Known-ID fragment admission plus hidden-position reconstruction check.

Endpoint SDK timestamps and lateral positions are recovered from the retained
raw buffer. Missing raw endpoint evidence excludes the case rather than inventing it.
"""
import argparse,json,time,sqlite3,math
from pathlib import Path
import numpy as np
from .archive_extension import cases
from .same_id_gaps import candidates
from .reconstruction_layers import prediction
from .reconstruction_study import metrics,summarize

def run(snapshot,report,buffer,limit=4):
    from dashboard.server import sites
    from .florida_rolling import geometry
    metadata={s['id']:s for s in geometry([s for s in sites() if s['id'] in {x['id'] for x in snapshot['sites']}])}
    db=sqlite3.connect(f'file:{buffer}?mode=ro',uri=True)
    rows=[];missing_raw=0
    def observation(site,tr,t):
        index=next((i for i,p in enumerate(tr['points']) if abs(p[0]-t)<1e-6),None)
        if index is None:return None
        offsets=tr.get('original_receipt_offsets_s')
        target=snapshot['start']+(offsets[index] if offsets is not None else t)
        row=db.execute('SELECT payload FROM frames WHERE site=? AND session=? AND received BETWEEN ? AND ? ORDER BY abs(received-?) LIMIT 1',
            (site['id'],tr['source_key'][0],target-.02,target+.02,target)).fetchone()
        if row is None:return None
        raw=json.loads(row[0]);frame=raw.get('frame',{});obj=next((o for o in frame.get('objects',[]) if str(o.get('id'))==tr['source_key'][1]),None)
        if obj is None:return None
        stamp=frame.get('timestamp') or raw.get('timestamp')
        if not stamp:return None
        m=metadata[site['id']];angle=math.radians(m.get('preview_rotation_deg',220))-math.radians(site.get('projection_bearing_deg',math.degrees(m['bearing'])))
        x=float(obj.get('centerX',0));y=float(obj.get('centerY',0))*(-1 if m.get('preview_mirror_y') else 1)
        return stamp,math.sin(angle)*x+math.cos(angle)*y
    for rank,site,tr,gap,(a,b,truth) in cases(snapshot,'test',limit):
        if gap>30:continue
        p=tr['points'];left=[q for q in p if q[0]<=a['t']];right=[q for q in p if q[0]>=b['t']]
        ea,eb=observation(site,tr,a['t']),observation(site,tr,b['t'])
        if ea is None or eb is None:missing_raw+=1;continue
        before={**tr,'points':left,'movement':{'state':'unknown'},'direction':'eastbound' if left[-1][1]>=left[0][1] else 'westbound','sensor_end':ea[0],'lateral_end_m':ea[1]}
        after={**tr,'points':right,'movement':{'state':'unknown'},'direction':'eastbound' if right[-1][1]>=right[0][1] else 'westbound','sensor_start':eb[0],'lateral_start_m':eb[1]}
        # Enforce the same visible-fragment movement filter as the renderer.
        visible_ok=all(abs(p[-1][1]-p[0][1])>=3 and abs(p[-1][1]-p[0][1])>=.7*sum(abs(v[1]-u[1]) for u,v in zip(p,p[1:])) for p in (left,right))
        eligible=list(candidates({'tracks':[before,after]},include_same_class=True)) if visible_ok else []
        row={'site':site['id'],'gap_s':gap,'rank':rank,'admitted':bool(eligible),'accepted':False}
        if eligible:
            candidate=eligible[0];points=prediction(candidate['a'],candidate['b'],report,exact_join=True)
            if points is not None:
                pred=np.asarray(points);pred[:,1]*=1 if tr['direction']=='eastbound' else -1
                row['accepted']=True;row['metrics']=metrics(pred,truth,report['calibration']['parameters'])
        rows.append(row)
    db.close()
    return {'missing_raw_endpoints':missing_raw,'created_at':time.time(),'time_basis':snapshot.get('time_basis','receipt'),'geometry_version':snapshot.get('geometry_version','inter-sensor-chord-v1'),
        'eligible':len(rows),'admitted':sum(r['admitted'] for r in rows),'accepted':sum(r['accepted'] for r in rows),
        'quality':summarize([r['metrics'] for r in rows if r['accepted']]),'cases':rows,
        'limitations':['Recorded positions hidden; ID identity is known within a continuous source track.',
            'SDK endpoint clock/lateral evidence is used; road alignment and sensor timezone remain provisional.',
            'Several mask lengths may reuse one vehicle.','No cross-sensor identity ground truth.','Strict estimator only; no endpoint correction in this check.']}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--snapshot',required=True);p.add_argument('--buffer',required=True);p.add_argument('--study',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    result=run(json.loads(Path(a.snapshot).read_text()),json.loads(Path(a.study).read_text()),a.buffer);Path(a.output).write_text(json.dumps(result,indent=2));print({k:v for k,v in result.items() if k!='cases'})
