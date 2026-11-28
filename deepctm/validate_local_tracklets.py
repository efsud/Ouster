"""Known-ID masking proxy for the local changed-ID matcher; not field identity truth."""
import json,hashlib,time,argparse
from pathlib import Path
from datetime import datetime,timedelta
from .local_tracklet_matching import reconstruct
from .reconstruction_layers import prediction
from .reconstruction_study import masked_case

def run(source,study,output):
    raw=Path(source).read_bytes();snapshot=json.loads(raw);report=json.loads(Path(study).read_text());rows=[]
    for site in snapshot['sites']:
        if site['id'] not in report['plan']['spatial_partitions']['test']:continue
        for direction in ('eastbound','westbound'):
            fragments=[];truth={};case_count=0
            for track in site['tracks']:
                if track['class_type']!='2' or track['direction']!=direction or track.get('movement',{}).get('movement') not in ('WE','EW'):continue
                if track['points'][0][0]<.8*(snapshot['end']-snapshot['start']):continue
                key=json.dumps([site['id'],track['source_key'],track['points'][0][0]])
                gap=(5,10)[int(hashlib.sha256(key.encode()).hexdigest()[:8],16)%2]
                case=masked_case(track,gap)
                if case is None:continue
                a,b,_=case
                left=[p for p in track['points'] if p[0]<=a['t']][-5:]
                right=[p for p in track['points'] if p[0]>=b['t']][:5]
                for side,points in [('left',left),('right',right)]:
                    tr=dict(track,points=points,source_key=[track['source_key'][0],f'{case_count}-{side}','2'])
                    # Mask endpoints use receipt-aligned clocks in this proxy.
                    origin=datetime(2026,1,1)
                    tr['sensor_start']=(origin+timedelta(seconds=points[0][0])).isoformat()
                    tr['sensor_end']=(origin+timedelta(seconds=points[-1][0])).isoformat()
                    fragments.append(tr);truth[(side,round(points[-1 if side=='left' else 0][0],2),round(points[-1 if side=='left' else 0][1],2))]=case_count
                case_count+=1
            # Reverse order prevents list order revealing the true pairs.
            paths=reconstruct({'id':site['id'],'tracks':fragments[::-1]},lambda a,b:prediction(a,b,report))
            correct=0
            for p in paths:
                a,b=p['points'][0],p['points'][-1]
                # Optimizer permits 1m endpoint tolerance; identify using time.
                aa={v for (side,t,x),v in truth.items() if side=='left' and abs(t-a[0])<.02 and abs(x-a[1])<1.01}
                bb={v for (side,t,x),v in truth.items() if side=='right' and abs(t-b[0])<.02 and abs(x-b[1])<1.01}
                correct+=len(aa)==len(bb)==1 and aa==bb
            rows.append(dict(site=site['id'],direction=direction,eligible=case_count,matched=len(paths),correct=correct,false=len(paths)-correct))
    totals={k:sum(r[k] for r in rows) for k in ('eligible','matched','correct','false')}
    result=dict(created_at=time.time(),source_sha256=hashlib.sha256(raw).hexdigest(),rows=rows,totals=totals,
        limitations=['Same-sensor synthetic ID changes, not independent vehicle-identity ground truth','Receipt-aligned proxy clocks do not test sensor clock offsets','Lateral values use visible fragment endpoints; this proxy does not simulate lane changes','5/10 s masks only; no parameter tuning in this evaluation'])
    Path(output).write_text(json.dumps(result,indent=2));return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--snapshot',required=True);p.add_argument('--study',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    print(run(a.snapshot,a.study,a.output)['totals'])
