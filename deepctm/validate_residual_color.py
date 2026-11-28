"""Fixed recorded-mask comparison of the requested residual association rule.

Scoring IDs never enter association. Local 2D/clock admission is tested
separately; this benchmark compares the endpoint association rule itself.
"""
import json,argparse,hashlib
from pathlib import Path
import numpy as np
from .validate_bidirectional import groups
from .bidirectional_association import associate as reference
from .color_slope import associate
from .corridor_campaign import subset,earlier_ids,atomic


def evaluate(snapshot,params):
    totals={kind:dict(eligible=0,baseline_correct=0,baseline_wrong=0,added_correct=0,added_wrong=0,added_position_errors_m=[]) for kind in ('temporal','spatial')}
    details=[]
    for group,rows in sorted(groups(snapshot).items()):
        rows=sorted(rows,key=lambda r:r[1]['t']);rows=rows[max(0,(len(rows)-40)//2):max(0,(len(rows)-40)//2)+40]
        kind=group[0]
        for scenario in ('complete','missing_arrivals'):
            ai=list(range(len(rows)));bi=[j for j,r in enumerate(rows) if scenario=='complete' or int(r[0][8:16],16)%4][::-1]
            left=[dict(rows[i][1],direction=group[2]) for i in ai];right=[dict(rows[j][2],direction=group[2]) for j in bi]
            baseline=reference(left,right,params,blend=.5);used_a={m['left'] for m in baseline};used_b={m['right'] for m in baseline}
            aa=[i for i in range(len(left)) if i not in used_a];bb=[j for j in range(len(right)) if j not in used_b]
            extra=associate([left[i] for i in aa],[right[j] for j in bb],max_gap=90 if kind=='temporal' else 120,max_residual=10 if kind=='temporal' else 20)
            total=totals[kind];total['eligible']+=len(bi)
            for m in baseline:total['baseline_correct' if rows[ai[m['left']]][0]==rows[bi[m['right']]][0] else 'baseline_wrong']+=1
            for m in extra:
                i,j=ai[aa[m['left']]],bi[bb[m['right']]];correct=rows[i][0]==rows[j][0]
                total['added_correct' if correct else 'added_wrong']+=1
                error=None
                if correct:
                    p=np.asarray(m['points']);truth=rows[i][3];error=float(np.mean(abs(np.interp(truth[:,0],p[:,0],p[:,1])-truth[:,1])));total['added_position_errors_m'].append(error)
                details.append(dict(kind=kind,site=group[1],direction=group[2],size=group[3],scenario=scenario,correct=correct,residual_m=m['residual_m'],position_mae_m=error))
    for total in totals.values():
        e=total.pop('added_position_errors_m');total['added_position_mae_m']=float(np.mean(e)) if e else None
        n=total['added_correct']+total['added_wrong'];total['added_precision']=total['added_correct']/n if n else None
    return dict(summary=totals,added_matches=details)


def run(output):
    path=Path(output);path.mkdir(parents=True,exist_ok=True)
    raw=Path('data/florida-rolling/snapshot.json').read_bytes();s=json.loads(raw);params=json.load(open('data/reconstruction/word-v1-collection/evaluation-001/report.json'))['calibration']['parameters']
    protocol=dict(snapshot_sha256=hashlib.sha256(raw).hexdigest(),window=[s['start'],s['end']],split=s['start']+1800,embargo_s=30,policy='Requested fixed method; no tuning. Same 1m/s speed-color band, chronological minimum discrepancy, existing endpoints reserved, ties unresolved. Evaluation is descriptive, not a claim of guaranteed identity.')
    atomic(path/'protocol.json',protocol)
    dev=evaluate(subset(s,0,1770),params);atomic(path/'development.json',dev)
    test=evaluate(subset(s,1830,3600,earlier_ids(s,1800)),params);atomic(path/'test.json',test)
    result=dict(state='complete',protocol=protocol,development=dev['summary'],test=test['summary'],limitations=['Additional rule is the requested experimental hypothesis layer, not recovered ground truth.','Same-sensor masks do not verify cross-sensor identities.','This endpoint benchmark omits production local lateral/clock gates; actual local recovery counts differ.','Repeated masks and complete/missing-arrival scenarios are correlated.'])
    atomic(path/'report.json',result);print(json.dumps(result),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);run(p.parse_args().output)
