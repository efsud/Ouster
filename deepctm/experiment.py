"""Prepare captured trajectories, fit the research model, and export held-out forecasts."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import time
import numpy as np
import torch
from .capture import atomic
from .features import prepare,split_sequences
from .model import DeepCTM,mass_error

ROOT=Path(__file__).resolve().parents[1]


def metrics(pred,target,mask):
    result={}
    for lead in [0,3]:
        delta=(pred[:,lead,:,0]-target[:,lead,:,0])[mask[:,lead]]
        truth=target[:,lead,:,0][mask[:,lead]]
        nonzero=truth.abs()>1e-6
        result[str((lead+1)*15)]={'rmse_veh_h':float(delta.square().mean().sqrt()),'mae_veh_h':float(delta.abs().mean()),'mape_pct':float((delta[nonzero]/truth[nonzero]).abs().mean()*100) if nonzero.any() else None,'mape_excluded_zero_targets':int((~nonzero).sum()),'observations':len(delta)}
    return result


def train_direction(x,mask,config,epochs,directory,name,start):
    torch.manual_seed(config['seed']);np.random.seed(config['seed']);torch.set_num_threads(1)
    context=config['context_steps'];horizon=config['horizon_steps'];splits=split_sequences(x,mask,context,horizon)
    counts={key:len(values) for key,values in splits.items()}
    if counts['train']<8 or counts['validation']<2 or counts['test']<2:
        return {'state':'insufficient_data','sequences':counts,'reason':'Need at least 8/2/2 complete training/validation/test sequences; gaps are not interpolated.'}
    def batch(indices):
        return tuple(torch.from_numpy(np.stack(a)) for a in [
            [x[i-context:i] for i in indices],[mask[i-context:i] for i in indices],
            [x[i:i+horizon] for i in indices],[mask[i:i+horizon] for i in indices]])
    train=batch(splits['train']);validation=batch(splits['validation']);test=batch(splits['test'])
    model=DeepCTM(config);optimizer=torch.optim.Adam(model.parameters(),lr=config['learning_rate'],weight_decay=config['weight_decay'])
    best=float('inf');best_state=None;history=[]
    for epoch in range(epochs):
        model.train();optimizer.zero_grad();output=model(train[0],train[1],horizon);loss,terms=model.loss(output,train[2],train[3])
        if not torch.isfinite(loss):raise ValueError('Nonfinite training loss')
        loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),5.);optimizer.step()
        model.eval()
        with torch.no_grad():
            out=model(validation[0],validation[1],horizon)
            # Model selection only on observed validation flow; no test tuning.
            selection=((out['prediction'][...,0]-validation[2][...,0])[validation[3]]).square().mean().item()
        history.append({'epoch':epoch+1,'training_loss':float(loss.detach()),'validation_flow_mse':selection})
        if selection<best:best=selection;best_state=copy.deepcopy(model.state_dict())
    model.load_state_dict(best_state);model.eval()
    with torch.no_grad():
        out=model(test[0],test[1],horizon);pred=out['prediction']
        persistence=test[0][:,-1:,].expand(-1,horizon,-1,-1)
        state=test[0][:,-1]/model.scales
        state[:,1:-1]=(state[:,:1]+state[:,-1:])/2
        pure=[]
        for _ in range(horizon):state,_=model.physics(state);pure.append(state*model.scales)
        pure=torch.stack(pure,1)
        # Each node predicts its outgoing flow; the upstream boundary remains the
        # CTM-admitted persisted demand. Internal edge flow is shared by adjacent cells.
        learned_flows=torch.cat([out['flows'][...,:1],pred[...,0]],-1)
        error=mass_error(out['previous'][...,1],pred[...,1],learned_flows,model.lengths,config['interval_s']/3600)
        correction_error=mass_error(out['previous'][...,1],pred[...,1],out['flows'],model.lengths,config['interval_s']/3600)
    directory=Path(directory)
    torch.save({'model_state':model.state_dict(),'config':config,'direction':name,'status':'provisional','feature_units':['veh/h','veh/km','km/h']},directory/(name+'.pt'))
    points=[]
    for j,index in enumerate(splits['test']):
        for lead in [0,3]:
            for node in [0,len(config['cell_lengths_km'])-1]:
                points.append({'forecast_origin':start+index*config['interval_s'],'target_start':start+(index+lead)*config['interval_s'],'target_end':start+(index+lead+1)*config['interval_s'],'lead_minutes':(lead+1)*15,'node':node,'observed_flow':float(test[2][j,lead,node,0]),'predicted_flow':float(pred[j,lead,node,0]),'persistence_flow':float(persistence[j,lead,node,0]),'ctm_flow':float(pure[j,lead,node,0])})
    return {'state':'trained_provisional','sequences':counts,'best_epoch':min(history,key=lambda h:h['validation_flow_mse'])['epoch'],'epochs':epochs,
        'metrics':metrics(pred,test[2],test[3]),'persistence':metrics(persistence,test[2],test[3]),'pure_ctm':metrics(pure,test[2],test[3]),
        'ctm_branch_correction_mass_error_vehicles':float(correction_error.mean()),
        'mmce_mean_all_cells_vehicles':float(error.mean()),'mmce_paper_observed_denominator_vehicles':float(error.sum()/(error.shape[0]*error.shape[1]*2)),
        'training_history':history,'held_out_forecasts':points}


def run(directory,epochs=40):
    directory=Path(directory);config=json.loads((directory/'config.json').read_text());manifest=json.loads((directory/'manifest.json').read_text())
    if manifest['state'] not in {'captured','experiment_complete','analysis_failed'}:raise ValueError('Capture must finish before training; never train from an unfinished gzip file')
    step=config['interval_s'];start=np.ceil(manifest['start']/step)*step;end=np.floor(manifest['end']/step)*step
    datasets,quality=prepare(directory,config,float(start),float(end))
    report={'version':config['version'],'status':'provisional research adaptation','start':float(start),'end':float(end),'clock':'receipt UTC; sensor clock offsets unverified','created_at':time.time(),'config':config,'quality':quality,'directions':{},'source_manifest_sha256':hashlib.sha256((directory/'manifest.json').read_bytes()).hexdigest()}
    for name,(x,mask) in datasets.items():
        np.savez_compressed(directory/(name+'-features.npz'),features=x,mask=mask,start=start,interval_s=step)
        report['directions'][name]=train_direction(x,mask,config,epochs,directory,name,start)
        atomic(directory/'report.json',report)
    atomic(ROOT/'data/deepctm/result.json',report)
    print(json.dumps({k:{'state':v['state'],'sequences':v['sequences']} for k,v in report['directions'].items()}))
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--capture',required=True);p.add_argument('--epochs',type=int,default=40);a=p.parse_args()
    if not 1<=a.epochs<=500:p.error('Use 1–500 epochs')
    run(a.capture,a.epochs)
