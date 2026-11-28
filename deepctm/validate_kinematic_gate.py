"""Compare legacy cubic vs exact kinematic gates on identical masked candidates."""
import argparse,json,time
from pathlib import Path
from .validate_shape_association import score
from .corridor_campaign import subset,earlier_ids,atomic
from .kinematic_gate import path

def run(snapshot,parameters,output,deadline=None):
    report={'selected_method':'kinematic_0.01','calibration':{'parameters':parameters}}
    duration=snapshot['end']-snapshot['start']
    test=subset(snapshot,.5*duration+30,duration,excluded=earlier_ids(snapshot,.5*duration))
    result={'window':[snapshot['start'],snapshot['end']],'parameters':parameters,'unpublished':True,
        'limitations':['Same-sensor spatial masks, not actual cross-sensor identity ground truth.',
        'Repeated scenarios are correlated. Parameters unchanged; this experiment does not authorize deployment.']}
    result['legacy']=score(test,report,[.5],limit=20,deadline=deadline)
    result['kinematic']=score(test,report,[.5],limit=20,deadline=deadline,path_gate=path)
    atomic(Path(output),result)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--snapshot',required=True);p.add_argument('--model',required=True);p.add_argument('--output',required=True);p.add_argument('--deadline',type=float)
    a=p.parse_args();run(json.loads(Path(a.snapshot).read_text()),json.loads(Path(a.model).read_text())['parameters'],a.output,a.deadline)
