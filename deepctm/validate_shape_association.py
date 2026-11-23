"""Chronological selection/test of shape-assisted association on spatial masks.

Frozen physics; size penalties selected using early-window validation only.
Vehicle IDs are used for scoring/exclusion, never passed to the matching cost.
"""
import argparse,json,time
from pathlib import Path
from .archive_extension import association_groups
from .corridor_campaign import subset,earlier_ids,atomic
from .shape_association import associate
from .reconstruction_layers import prediction
from .matching_physics import associate as current_associate

def score(snapshot,report,weights,limit=25,deadline=None,path_gate=None):
    groups=association_groups(snapshot,'test');records=[];cache={};stopped=False
    for group,rows in sorted(groups.items()):
        if deadline is not None and time.time()>=deadline:stopped=True;break
        rows=sorted(rows)[:limit]
        for scenario in ('complete','missing_endpoints'):
            ai=[i for i,r in enumerate(rows) if scenario=='complete' or int(r[0][8:16],16)%5]
            bi=[i for i,r in enumerate(rows) if scenario=='complete' or int(r[0][16:24],16)%4][::-1]
            left=[rows[i][1] for i in ai];right=[rows[i][2] for i in bi]
            for weight in weights:
                proposed=current_associate(left,right,report['calibration']['parameters']) if weight=='current' else associate(left,right,report['calibration']['parameters'],weight=weight,path_gate=path_gate)
                accepted=[]
                for match in proposed:
                    i,j=ai[match['left']],bi[match['right']];key=(*group,i,j)
                    if key not in cache:cache[key]=prediction(rows[i][1],rows[j][2],report,exact_join=True) is not None
                    if cache[key]:accepted.append((i,j))
                correct=sum(i==j for i,j in accepted)
                records.append({'site':group[0],'direction':group[1],'width':group[2],'scenario':scenario,'weight':weight,
                    'eligible':len(set(ai)&set(bi)),'matched':len(accepted),'correct':correct,'false':len(accepted)-correct})
    totals={str(w):{k:sum(r[k] for r in records if r['weight']==w) for k in ('eligible','matched','correct','false')} for w in weights}
    return {'state':'deadline_reached' if stopped else 'complete','totals':totals,'groups':records}

def run(snapshot,report,output):
    length=snapshot['end']-snapshot['start'];validation=subset(snapshot,0,.5*length-30)
    test=subset(snapshot,.5*length+30,length,excluded=earlier_ids(snapshot,.5*length))
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    result={'state':'validating','window':[snapshot['start'],snapshot['end']],'time_basis':snapshot.get('time_basis','receipt'),
        'geometry_version':snapshot.get('geometry_version'),'parameters':report['calibration']['parameters'],
        'limitations':['Single-sensor masked bands, not actual intersensor identity ground truth.','Cross-sensor box-size biases remain unverified.','Scenarios reuse vehicles; counts are not independent.','No ground-truth intermediate road trajectories.']}
    result['validation']=score(validation,report,[0,.1,.25,.5]);base=result['validation']['totals']['0']
    eligible=[w for w in (0,.1,.25,.5) if result['validation']['totals'][str(w)]['false']<=base['false'] and result['validation']['totals'][str(w)]['correct']>=base['correct']]
    winner=min(eligible,key=lambda w:(-result['validation']['totals'][str(w)]['correct'],result['validation']['totals'][str(w)]['false'],w))
    result.update(selected_weight=winner,state='testing');atomic(output/'report.json',result)
    result['test']=score(test,report,[0] if winner==0 else [0,winner]);result['state']='complete';atomic(output/'report.json',result)
    print({'selected_weight':winner,'validation':result['validation']['totals'],'test':result['test']['totals']},flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--snapshot',required=True);p.add_argument('--study',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    run(json.loads(Path(a.snapshot).read_text()),json.loads(Path(a.study).read_text()),a.output)
