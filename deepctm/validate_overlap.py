"""Known-ID overlap proxy using disjoint interleaved recorded observations.

The two views share one detector's calibration/errors, unlike actual sensors.
Perturbed-clock/position scenarios are explicitly synthetic robustness tests.
"""
import argparse,hashlib,json
from pathlib import Path
from .object_shape import summarize
from .overlap_association import associate,evidence

def views(track,center,half_width=20):
    sign=1 if track['direction']=='eastbound' else -1
    p=track['points'];dims=track.get('dimensions',[None]*len(p));up=[];down=[];up_dims=[];down_dims=[]
    for i,row in enumerate(p):
        if i%2==0 and row[1]*sign<=center*sign+half_width:up.append(row);up_dims.append(dims[i])
        if i%2==1 and row[1]*sign>=center*sign-half_width:down.append(row);down_dims.append(dims[i])
    a=dict(direction=track['direction'],points=up,shape_end=summarize(up_dims[-5:]))
    b=dict(direction=track['direction'],points=down,shape_start=summarize(down_dims[:5]))
    return (a,b) if evidence(a,b) is not None else None

def run(snapshot,limit=30):
    groups={}
    for site in snapshot['sites']:
        for track in site['tracks']:
            if track['class_type']!='2':continue
            pair=views(track,site['station_m'])
            if pair is None:continue
            rank=hashlib.sha256(json.dumps([site['id'],track['source_key'],track['points'][0][0]]).encode()).hexdigest()
            groups.setdefault((site['id'],track['direction']),[]).append((rank,*pair))
    records=[]
    for group,rows in sorted(groups.items()):
        rows=sorted(rows)[:limit]
        for scenario,shift_m,shift_s in [('recorded_interleaved',0,0),('synthetic_position_bias_2m',2,0),('synthetic_clock_bias_0_25s',0,.25)]:
            for missing in (False,True):
                ai=[i for i,r in enumerate(rows) if not missing or int(r[0][8:16],16)%5]
                bi=[i for i,r in enumerate(rows) if not missing or int(r[0][16:24],16)%4][::-1]
                left=[rows[i][1] for i in ai];right=[dict(rows[i][2],points=[[t+shift_s,x+shift_m,v] for t,x,v in rows[i][2]['points']]) for i in bi]
                matches=associate(left,right);correct=sum(ai[m['left']]==bi[m['right']] for m in matches)
                records.append({'site':group[0],'direction':group[1],'scenario':scenario,'missing_endpoints':missing,
                                'eligible':len(set(ai)&set(bi)),'matched':len(matches),'correct':correct,'false':len(matches)-correct})
    totals={scenario:{k:sum(r[k] for r in records if r['scenario']==scenario) for k in ('eligible','matched','correct','false')} for scenario in sorted({r['scenario'] for r in records})}
    return {'window':[snapshot['start'],snapshot['end']],'totals':totals,'groups':records,
            'limitations':['Interleaved frames are real observations, but both views share one detector calibration and noise.','Selection requires an observable known-pair overlap; counts are conditional on support.','Clock/position perturbations are synthetic tests, not measured cross-sensor errors.','No actual cross-sensor identities verified.','Scenarios reuse vehicles.','No production association rule changed.']}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--snapshot',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    r=run(json.loads(Path(a.snapshot).read_text()));Path(a.output).parent.mkdir(parents=True,exist_ok=True);Path(a.output).write_text(json.dumps(r,indent=2));print(r['totals'])
