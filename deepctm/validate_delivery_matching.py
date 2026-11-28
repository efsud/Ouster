"""Identity-blind spatial matching comparison using paired time bases.

Both sides contain the same measured fragments; identity is used only for score.
This cannot establish actual identity across different sensors.
"""
import json,hashlib,argparse
from pathlib import Path
from collections import defaultdict
import numpy as np
from .corridor_campaign import subset,earlier_ids,identity,atomic
from .validate_spatial import masked
from .spatial_bridges import endpoint
from .bidirectional_association import associate,motion_context


def evaluate(s,params):
    groups=defaultdict(list)
    for site in s['sites']:
        for tr in site['tracks']:
            if tr['class_type']!='2':continue
            rank=hashlib.sha256(identity(site,tr).encode()).hexdigest()
            width=(20,50,100)[int(rank[:8],16)%3];m=masked(tr,site['station_m'],width)
            if m is None:continue
            a,b=m[:2];p=np.asarray(tr['points']);received=p.copy();received[:,0]=tr['original_receipt_offsets_s']
            i=int(np.argmin(abs(p[:,0]-a['t'])));j=int(np.argmin(abs(p[:,0]-b['t'])))
            pairs={}
            for method,values in [('receipt',received),('corrected',p)]:
                left=endpoint(values[:i+1],True);right=endpoint(values[j:],False)
                if left and right:
                    pairs[method]=(dict(left,class_type='2',shape=a.get('shape'),motion_context=motion_context(values[:i+1],True)),dict(right,class_type='2',shape=b.get('shape'),motion_context=motion_context(values[j:],False)))
            affected=bool(np.max(abs(received[max(0,i-5):j+6,0]-p[max(0,i-5):j+6,0]))>.1)
            groups[site['id'],tr['direction'],width].append((rank,pairs,affected,a['t']))
    totals={name:dict(correct=0,wrong=0,eligible=0,affected_correct=0,affected_wrong=0,affected_eligible=0) for name in ('receipt','corrected')}
    for group,rows in groups.items():
        rows=sorted(rows,key=lambda r:r[3]);rows=rows[max(0,(len(rows)-100)//2):max(0,(len(rows)-100)//2)+100]
        for scenario in ('all','missing_arrivals'):
            for name,total in totals.items():
                left_ids=[i for i,r in enumerate(rows) if name in r[1]]
                right_ids=[i for i in left_ids if scenario=='all' or int(rows[i][0][8:16],16)%4][::-1]
                matches=associate([rows[i][1][name][0] for i in left_ids],[rows[j][1][name][1] for j in right_ids],params,blend=.5)
                # Same denominator across methods, including unavailable context.
                total['eligible']+=sum(scenario=='all' or int(r[0][8:16],16)%4!=0 for r in rows)
                total['affected_eligible']+=sum(r[2] and (scenario=='all' or int(r[0][8:16],16)%4!=0) for r in rows)
                for m in matches:
                    i,j=left_ids[m['left']],right_ids[m['right']];correct=rows[i][0]==rows[j][0]
                    total['correct' if correct else 'wrong']+=1
                    if rows[i][2] or rows[j][2]:total['affected_correct' if correct else 'affected_wrong']+=1
    return totals


def run(output):
    s=json.load(open('/tmp/florida-debursted-candidate.json'));params=json.load(open('data/reconstruction/word-v1-collection/evaluation-001/report.json'))['calibration']['parameters'];out=Path(output)
    atomic(out/'matching-protocol.json',dict(window=[s['start'],s['end']],gates='No increase in false matches and no loss of correct matches on early and later excluded-ID partitions. Fixed parameters; widths 20/50/100m; complete and missing-arrival cases.'))
    dev=evaluate(subset(s,0,1770),params);atomic(out/'matching-development.json',dev)
    test=evaluate(subset(s,1830,3600,earlier_ids(s,1800)),params)
    result=dict(development=dev,test=test,eligible=all(r['corrected']['wrong']<=r['receipt']['wrong'] and r['corrected']['correct']>=r['receipt']['correct'] for r in (dev,test)),limitations=['Same-sensor masked-road proxy; actual sensor-to-sensor identities and clock offsets unverified.','Overlapping masks and scenarios are correlated.','Candidates selected from corrected continuous tracks; not corridor recall.'])
    atomic(out/'matching-validation.json',result);print(json.dumps(result),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);run(p.parse_args().output)
