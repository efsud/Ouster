"""Repeatable interpolation diagnostic: hide recorded points, retain flanks.

No hidden position or speed enters fitting. Same-track identity is provided;
this measures interpolation error, not identity accuracy or repaired clocks.
The frozen development hour is not an untouched external test recording.
"""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import numpy as np
from .local_gaps import VEHICLES
from .same_id_continuity import curve,velocity


def validate(snapshot):
    rows=[];used=set();counts=defaultdict(int)
    for site in snapshot['sites']:
        for tr in site['tracks']:
            if tr.get('class_type') not in VEHICLES:continue
            segments=[[]]
            for p in tr['points']:
                if segments[-1] and not 0<p[0]-segments[-1][-1][0]<=1.5:segments.append([])
                segments[-1].append(p)
            for segment in segments:
                if len(segment)<10:continue
                data=np.array(segment);times=data[:,0]
                for seconds in (3,5,10,20,40,60,120):
                    key=(site['id'],tuple(tr['source_key'][:2]),seconds)
                    if key in used or counts[site['id'],seconds]>=50:continue
                    left=int(np.searchsorted(times,times[0]+2))
                    if left>=len(data)-1:continue
                    right=int(np.searchsorted(times,times[left]+seconds))
                    if right>=len(data)-1 or times[-1]-times[right]<2 or right-left<3:continue
                    before=segment[:left+1];after=segment[right:]
                    predicted=curve(before[-1],after[0],velocity(before,True),velocity(after,False))
                    if predicted is None:continue
                    pts=np.array(predicted[0]);truth=data[left+1:right]
                    estimates=np.interp(truth[:,0],pts[:,0],pts[:,1]);speeds=np.interp(truth[:,0],pts[:,0],pts[:,2])
                    linear=np.interp(truth[:,0],[times[left],times[right]],[data[left,1],data[right,1]])
                    used.add(key);counts[site['id'],seconds]+=1
                    rows.append(dict(site=site['id'],identity=list(tr['source_key'][:2]),gap_s=seconds,
                        actual_gap_s=float(times[right]-times[left]),start=float(times[left]),
                        position_mae_m=float(np.mean(abs(estimates-truth[:,1]))),
                        position_max_error_m=float(np.max(abs(estimates-truth[:,1]))),
                        linear_mae_m=float(np.mean(abs(linear-truth[:,1]))),
                        reported_speed_mae_mps=float(np.mean(abs(speeds-truth[:,2])))))
    def summary(rs):
        if not rs:return {'masks':0}
        return dict(masks=len(rs),distinct_ids=len({(r['site'],tuple(r['identity'])) for r in rs}),
            position_mae_m=float(np.mean([r['position_mae_m'] for r in rs])),
            p95_case_mae_m=float(np.quantile([r['position_mae_m'] for r in rs],.95)),
            linear_mae_m=float(np.mean([r['linear_mae_m'] for r in rs])),
            reported_speed_mae_mps=float(np.mean([r['reported_speed_mae_mps'] for r in rs])))
    return dict(state='complete',pooled=summary(rows),by_duration={str(s):summary([r for r in rows if r['gap_s']==s]) for s in (3,5,10,20,40,60,120)},
        by_site={s['id']:summary([r for r in rows if r['site']==s['id']]) for s in snapshot['sites']},
        limitations=['Fixed development benchmark; not independent final validation.',
            'Identity supplied by continuous recorded track. No cross-sensor matching evaluated.',
            'Masks from one vehicle can be correlated. No hidden targets used in interpolation.',
            'No clock conflicts are injected; gray timing connectors have no tested motion accuracy.',
            'Speed comparison uses reported object speed against a projected-position derivative.'],cases=rows)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--snapshot',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();raw=args.snapshot.read_bytes();result=validate(json.loads(raw));result['snapshot_sha256']=hashlib.sha256(raw).hexdigest()
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,allow_nan=False))
    print(json.dumps({k:v for k,v in result.items() if k not in ('cases','by_site')}))
