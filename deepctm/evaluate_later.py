"""Evaluate a frozen checkpoint on later data; no optimization or checkpoint selection."""
import argparse,json
from pathlib import Path
import numpy as np
import torch
from .model import DeepCTM
from .pair_train import score

def run(experiment,later):
    torch.set_num_threads(1);root=Path(experiment);later=Path(later)
    manifest=json.loads((later/'manifest.json').read_text());data=np.load(later/'features.npz');report={'checkpoint':str(root),'evaluation':str(later),'directions':{},'selection':'No fitting; all contexts start at or after evaluation_not_before; nonoverlapping context-plus-target windows'}
    for direction in ['eastbound','westbound']:
        ck=torch.load(root/(direction+'.pt'),weights_only=False,map_location='cpu');cfg=ck['config'];model=DeepCTM(cfg);model.load_state_dict(ck['state_dict']);model.eval()
        x=data[direction];mask=data[direction+'_mask'];fm=data[direction+'_feature_mask'];c=cfg['context_steps'];h=cfg['horizon_steps'];step=cfg['interval_s']
        first=max(c,int(np.ceil((manifest['evaluation_not_before']-float(data['start']))/step))+c)
        ids=[i for i in range(first,len(x)-h+1,c+h) if mask[i-c:i,[0,-1]].mean(axis=0).min()>=.8 and mask[i:i+h,[0,-1]].mean(axis=0).min()>=.8]
        if not ids:report['directions'][direction]={'state':'insufficient_data'};continue
        inputs=torch.tensor(np.stack([x[i-c:i] for i in ids]));im=torch.tensor(np.stack([mask[i-c:i] for i in ids]));iff=torch.tensor(np.stack([fm[i-c:i] for i in ids]));target=torch.tensor(np.stack([x[i:i+h] for i in ids]));valid=torch.tensor(np.stack([fm[i:i+h] for i in ids]))
        with torch.no_grad():
            pred=model(inputs,im,h,iff)['prediction'];last=torch.zeros_like(inputs[:,0]);last[...,2]=cfg['free_speed_kmh']
            for j in range(c):last=torch.where(iff[:,j],inputs[:,j],last)
            for j in range(1,model.n-1):last[:,j]=last[:,0]+(last[:,-1]-last[:,0])*j/(model.n-1)
            persistence=last[:,None].expand_as(pred);state=last/model.scales;pure=[]
            for _ in range(h):state,_=model.physics(state);pure.append(state*model.scales)
        report['directions'][direction]={'n_windows':len(ids),'origin_bins':ids,'deepctm':score(pred,target,valid,step),'persistence':score(persistence,target,valid,step),'pure_ctm':score(torch.stack(pure,1),target,valid,step)}
    (root/'later-evaluation.json').write_text(json.dumps(report,indent=2));return report
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--experiment',required=True);p.add_argument('--later',required=True);a=p.parse_args();run(a.experiment,a.later)
