"""Unpublished per-class kinematic transfer study on recorded observations.

Training parameters use only the first half. Final-quarter identity-separated
masks report error/availability separately; no class is enabled automatically.
"""
import argparse,json,time,hashlib
from pathlib import Path
import numpy as np
from .archive_extension import cases
from .corridor_campaign import subset,earlier_ids,atomic,evaluate

def calibration(snapshot,class_type):
    speeds=[];acc=[];ids=set()
    for site in snapshot['sites']:
        for tr in site['tracks']:
            if tr['class_type']!=class_type:continue
            p=np.asarray(tr['points'],float);dt=np.diff(p[:,0]);valid=(dt>0)&(dt<=1.5)
            speeds.extend(p[:,2][p[:,2]>=0]);acc.extend((np.diff(p[:,2])[valid]/dt[valid]).tolist());ids.add((site['id'],*tr['source_key'][:2]))
    evidence={'distinct_training_ids':len(ids),'speed_samples':len(speeds),'acceleration_samples':len(acc)}
    if len(ids)<10 or min(len(speeds),len(acc))<100:return None,evidence
    return {'vmax':float(np.clip(np.quantile(speeds,.995),5,35)),
        'amin':float(np.clip(np.quantile(acc,.01),-6,-1)),
        'amax':float(np.clip(np.quantile(acc,.99),1,4))},evidence

def run(region,output,deadline):
    root=Path(__file__).resolve().parents[1];raw=(root/f'data/{region}-rolling/snapshot.json').read_bytes();s=json.loads(raw)
    car=json.loads((root/f'data/reconstruction/eight-hour-20261123/{region}/model.json').read_text())['parameters']
    training=subset(s,0,1770);test=subset(s,2730,3600,earlier_ids(s,2700));result={}
    for cls in ('4','5','8'):
        params,evidence=calibration(training,cls);entry={'training':evidence,'parameters':params,'state':'insufficient_training'};result[cls]=entry
        if params is None:continue
        rows=cases(test,'test',5,classes=(cls,))
        entry.update(state='evaluated',eligible=len(rows),car_parameter_transfer=evaluate(rows,car,deadline),class_parameters=evaluate(rows,params,deadline))
    report={'region':region,'window':[s['start'],s['end']],'snapshot_sha256':hashlib.sha256(raw).hexdigest(),'transform_manifest':s.get('transform_manifest'),'classes':result,
        'split':'First half training; final quarter testing, 30-second embargo and all earlier IDs excluded; no hyperparameter selection or publication',
        'limitations':['Local temporal masks only; actual intersensor identity remains unverified.','Class labels are vendor classifications, not manually confirmed vehicles.','Class 8 may represent a trailer; not automatically an independent traffic vehicle.','No production class filter changed.']}
    atomic(Path(output),report)
    for cls,r in result.items():print(region,cls,r['state'],r.get('eligible'),{k:v['summary']['strict'] for k,v in r.items() if k in ('car_parameter_transfer','class_parameters')},flush=True)
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--region',choices=['florida','finch'],required=True);p.add_argument('--output',required=True);p.add_argument('--deadline',type=float,required=True);a=p.parse_args();run(a.region,a.output,a.deadline)
