"""Association regression under recorded-trajectory fragmentation.

This is same-sensor proxy truth, not verification of cross-sensor identities.
Only a physically accepted same-ID local bridge marks a precursor as internal.
"""
import json,hashlib,argparse
from pathlib import Path
from collections import defaultdict
from .validate_bidirectional import groups
from .corridor_campaign import identity,subset,earlier_ids,atomic
from .spatial_bridges import endpoint
from .bidirectional_association import associate,motion_context
from .reconstruction_layers import prediction


def evaluate(snapshot,report):
    originals=defaultdict(list)
    for s in snapshot['sites']:
        for t in s['tracks']:
            originals[hashlib.sha256(identity(s,t).encode()).hexdigest()].append(t)
    totals={name:dict(correct=0,wrong_identity=0,premature_endpoint=0,eligible=0,internal_candidates=0) for name in ('baseline','terminals')}
    for group,rows in sorted(groups(snapshot).items()):
        if group[0]!='spatial':continue
        rows=sorted(rows,key=lambda r:r[1]['t'])[:30]
        left=[];tags=[];right=[];rkeys=[];internal=[]
        for key,a,b,truth in rows:
            left.append(a);tags.append(key);internal.append(False)
            right.append(b);rkeys.append(key)
            if int(key[:8],16)%2:continue
            source=next((t for t in originals[key] if t['points'][0][0]<=a['t']-7 and t['points'][-1][0]>=a['t']),None)
            if source is None:continue
            before=[p for p in source['points'] if p[0]<=a['t']-5]
            after=[p for p in source['points'] if a['t']-3<=p[0]<=a['t']]
            pre=endpoint(before,True);resume=endpoint(after,False)
            if not pre or not resume or prediction(pre,resume,report,exact_join=True) is None:continue
            pre=dict(pre,class_type='2',motion_context=motion_context(before,True))
            left.append(pre);tags.append(key);internal.append(True)
        for name in totals:
            keep=[i for i in range(len(left)) if name=='baseline' or not internal[i]]
            matches=associate([left[i] for i in keep],right,report['calibration']['parameters'],blend=.5)
            total=totals[name];total['eligible']+=len(rows);total['internal_candidates']+=sum(internal)
            for m in matches:
                i=keep[m['left']];j=m['right']
                kind='wrong_identity' if tags[i]!=rkeys[j] else 'premature_endpoint' if internal[i] else 'correct'
                total[kind]+=1
    return totals


def run(output):
    s=json.load(open('data/florida-rolling/snapshot.json'));r=json.load(open('data/reconstruction/word-v1-collection/evaluation-001/report.json'))
    path=Path(output);path.mkdir(parents=True,exist_ok=True)
    protocol=dict(window=[s['start'],s['end']],split=s['start']+1800,embargo_s=30,rule='At least as many correct terminal matches and no increase in wrong identities on development and later excluded-ID test. No threshold tuning.',limitations=['Artificial fragmentation of recorded same-sensor tracks; cross-sensor truth unavailable.','Existing accepted same-ID bridges supply internal-endpoint evidence; no inferred positions used in endpoint speed fits.'])
    atomic(path/'terminal-protocol.json',protocol)
    dev=evaluate(subset(s,0,1770),r);atomic(path/'terminal-development.json',dev)
    test=evaluate(subset(s,1830,3600,earlier_ids(s,1800)),r)
    ok=all(x['terminals']['correct']>=x['baseline']['correct'] and x['terminals']['wrong_identity']<=x['baseline']['wrong_identity'] for x in (dev,test))
    result=dict(protocol=protocol,development=dev,test=test,eligible=ok)
    atomic(path/'terminal-validation.json',result);print(json.dumps(result),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);run(p.parse_args().output)
