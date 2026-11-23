"""Blind association of overlapping views sampled from recorded local tracks.

Alternating real observations form two views; no intermediate observations are
invented. This tests association logic, not independent sensor calibration.
"""
import argparse,json,time,hashlib
from pathlib import Path
import numpy as np
from .corridor_campaign import subset,earlier_ids,atomic,identity
from .overlap_association import associate,evidence
from .object_shape import summarize as shape

def views(track,width):
    p=np.asarray(track['points'],float);sign=1 if track['direction']=='eastbound' else -1
    x=p[:,1]*sign
    if len(p)<12 or x[-1]-x[0]<width+20 or np.any(np.diff(p[:,0])>1.5):return None
    center=(x[0]+x[-1])/2
    indices=np.arange(len(p))
    left=indices[(x<=center+width/2)&(indices%2==0)]
    right=indices[(x>=center-width/2)&(indices%2==1)]
    if min(len(left),len(right))<5:return None
    dims=track.get('dimensions',[])
    def view(indices):
        sizes=[dims[i] for i in indices if i<len(dims)]
        return {'direction':track['direction'],'points':p[indices].tolist(),
                'shape_start':shape(sizes[:5]),'shape_end':shape(sizes[-5:])}
    return view(left),view(right)

def run(region,output,deadline):
    root=Path(__file__).resolve().parents[1];raw=(root/f'data/{region}-rolling/snapshot.json').read_bytes();s=json.loads(raw)
    test=subset(s,2730,3600,earlier_ids(s,2700));groups={}
    for site in test['sites']:
        for tr in site['tracks']:
            if tr['class_type']!='2':continue
            rank=hashlib.sha256((identity(site,tr)+str(tr['points'][0][0])).encode()).hexdigest()
            for width in (20,40,60):
                pair=views(tr,width)
                if pair:groups.setdefault((site['id'],tr['direction'],width),[]).append((rank,*pair))
    records=[]
    for (site,direction,width),rows in sorted(groups.items()):
        if time.time()>=deadline:break
        rows=sorted(rows)[:25]
        for scenario in ('complete','missing_endpoints'):
            ai=[i for i,r in enumerate(rows) if scenario=='complete' or int(r[0][:8],16)%5]
            bi=[i for i,r in enumerate(rows) if scenario=='complete' or int(r[0][8:16],16)%4][::-1]
            found=associate([rows[i][1] for i in ai],[rows[j][2] for j in bi])
            correct=sum(ai[m['left']]==bi[m['right']] for m in found)
            supported=sum(evidence(rows[i][1],rows[i][2]) is not None for i in set(ai)&set(bi))
            records.append({'site':site,'direction':direction,'width_m':width,'scenario':scenario,
                'eligible':len(set(ai)&set(bi)),'known_pair_overlap_supported':supported,'correct':correct,'false':len(found)-correct,'matched':len(found)})
    result={'state':'complete' if time.time()<deadline else 'deadline_reached','region':region,
        'window':[s['start'],s['end']],'snapshot_sha256':hashlib.sha256(raw).hexdigest(),
        'transform_manifest':s.get('transform_manifest'),'groups':records,
        'totals':{k:sum(r[k] for r in records) for k in ('eligible','known_pair_overlap_supported','matched','correct','false')},
        'limitations':['Both views come from one sensor; not independent sensor measurements.',
        'No sensor clock/position bias is fitted or validated by this test.',
        'Scenarios and widths can reuse vehicles; counts are correlated.',
        'No estimated gap is needed inside observed overlapping coverage.',
        'No production association or observations changed.']}
    atomic(Path(output),result);print(region,result['totals'],flush=True);return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--region',choices=['florida','finch'],required=True);p.add_argument('--output',required=True);p.add_argument('--deadline',type=float,required=True)
    a=p.parse_args();run(a.region,a.output,a.deadline)
