"""Chronological masked training/evaluation for the Palm Springs--Boston link."""
import argparse,copy,json,time,hashlib
from pathlib import Path
import numpy as np
import torch
from .model import DeepCTM,mass_error
from .florida_pair import pair_sequences
from .capture import atomic


def score(pred,target,valid,interval):
    report={}
    for lead in sorted({0,min(5,pred.shape[1]-1),pred.shape[1]-1}):
        rows={}
        for j,unit in enumerate(['flow_veh_h','density_veh_km','speed_kmh']):
            delta=(pred[:,lead,:,j]-target[:,lead,:,j])[valid[:,lead,:,j]]
            rows[unit]={'n':len(delta),'rmse':float(delta.square().mean().sqrt()) if len(delta) else None,'mae':float(delta.abs().mean()) if len(delta) else None}
        report[str((lead+1)*interval)]=rows
    return report


def run(directory,epochs=None):
    torch.set_num_threads(1);directory=Path(directory);config=json.loads((directory/'config.json').read_text())
    epochs=epochs or config['epochs'];data=np.load(directory/'features.npz');start=float(data['start'])
    report={'state':'training','method':'Independent DeepCTM adaptation; CTM physical core with directional GNN, LSTM, gate and PEC',
            'source_hashes':{name:hashlib.sha256((Path(__file__).parent/name).read_bytes()).hexdigest() for name in ['model.py','features.py','florida_pair.py','pair_train.py']},
            'created_at':time.time(),'start':start,'end':float(data['end']),'interval_s':config['interval_s'],'directions':{},
            'limitations':config['assumptions']+['Endpoint metrics do not establish accuracy inside the blind segment.','Neural corrections are not exactly mass-conserving; numerical discrepancy is reported.']}
    atomic(directory/'report.json',report)
    for direction in ['eastbound','westbound']:
        torch.manual_seed(config['seed']);x=data[direction];mask=data[direction+'_mask'];fm=data[direction+'_feature_mask'];c=config['context_steps'];h=config['horizon_steps']
        splits=pair_sequences(mask,c,h);counts={k:len(v) for k,v in splits.items()}
        if any(counts[k]<v for k,v in [('train',8),('validation',2),('test',2)]):
            report['directions'][direction]={'state':'insufficient_data','counts':counts};continue
        def batch(ids):
            return tuple(torch.from_numpy(np.stack(v)) for v in [[x[i-c:i] for i in ids],[mask[i-c:i] for i in ids],[fm[i-c:i] for i in ids],
                 [x[i:i+h] for i in ids],[mask[i:i+h] for i in ids],[fm[i:i+h] for i in ids]])
        train,val,test=[batch(splits[k]) for k in ['train','validation','test']]
        cfg={**config,'cell_lengths_km':config['cell_lengths_km'] if direction=='eastbound' else config['cell_lengths_km'][::-1]}
        model=DeepCTM(cfg);opt=torch.optim.Adam(model.parameters(),lr=cfg['learning_rate'],weight_decay=cfg['weight_decay'])
        best=float('inf');weights=None;best_epoch=0;history=[]
        for epoch in range(epochs):
            model.train();opt.zero_grad();out=model(train[0],train[1],h,train[2]);loss,terms=model.loss(out,train[3],train[4],train[5])
            if not torch.isfinite(loss):raise ValueError('Nonfinite loss')
            loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),5);opt.step();model.eval()
            with torch.no_grad():
                predicted=model(val[0],val[1],h,val[2])['prediction']
                scale=predicted.new_tensor(cfg.get('data_loss_scales',model.scales.tolist()))
                errors=((predicted-val[3])/scale).square();feature_counts=val[5].sum(dim=(0,1,2))
                metric=(((errors*val[5]).sum(dim=(0,1,2))/feature_counts.clamp_min(1))[feature_counts>0].mean() if cfg.get('balanced_features',False) else errors[val[5]].mean()).item()
            history.append({'epoch':epoch+1,'loss':float(loss.detach()),'validation_normalized_mse':metric})
            if metric<best:best=metric;weights=copy.deepcopy(model.state_dict());best_epoch=epoch+1
            if epoch%10==0:print(direction,'epoch',epoch+1,'validation',round(metric,5),flush=True)
        model.load_state_dict(weights);model.eval()
        with torch.no_grad():
            out=model(test[0],test[1],h,test[2]);pred=out['prediction']
            # Most recent available feature from input context only; no future values.
            last=test[0][:,0].clone()
            for j in range(c):last=torch.where(test[2][:,j],test[0][:,j],last)
            for node in range(1,model.n-1):last[:,node]=last[:,0]+(last[:,-1]-last[:,0])*node/(model.n-1)
            persist=last[:,None].expand_as(pred);state=last/model.scales
            for j in range(1,model.n-1):state[:,j]=state[:,0]+(state[:,-1]-state[:,0])*j/(model.n-1)
            pure=[]
            for _ in range(h):state,_=model.physics(state);pure.append(state*model.scales)
            pure=torch.stack(pure,1)
            flows=torch.cat([out['flows'][...,:1],pred[...,0]],-1)
            residual=mass_error(out['previous'][...,1],pred[...,1],flows,model.lengths,cfg['interval_s']/3600)
        torch.save({'state_dict':model.state_dict(),'config':cfg,'direction':direction},directory/(direction+'.pt'))
        np.savez_compressed(directory/(direction+'-heldout.npz'),prediction=pred.numpy(),target=test[3].numpy(),feature_mask=test[5].numpy(),
                            persistence=persist.numpy(),pure_ctm=pure.numpy(),origin_bins=np.array(splits['test']))
        result={'state':'trained_provisional','counts':counts,'best_epoch':best_epoch,'split_target_bins':splits,'history':history,
                'deepctm':score(pred,test[3],test[5],cfg['interval_s']),'persistence':score(persist,test[3],test[5],cfg['interval_s']),
                'pure_ctm':score(pure,test[3],test[5],cfg['interval_s']),'mean_mass_residual_vehicles':float(residual.mean()),'max_mass_residual_vehicles':float(residual.max())}
        report['directions'][direction]=result;atomic(directory/'report.json',report)
        print(direction,'finished',counts,flush=True)
    report['state']='evaluated';atomic(directory/'report.json',report)
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--experiment',required=True);p.add_argument('--epochs',type=int);a=p.parse_args();run(a.experiment,a.epochs)
