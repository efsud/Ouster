"""Exploratory one-minute DeepCTM adaptation; paths are virtual tracers, not identities."""
import argparse,copy,json,math
from pathlib import Path
import numpy as np
import torch
from .features import extract_site,events,split_sequences
from .model import DeepCTM,mass_error
from .capture import atomic


def fit(x,mask,c,epochs):
    splits=split_sequences(x,mask,4,1)
    counts={k:len(v) for k,v in splits.items()}
    if any(counts[k]<n for k,n in [('train',8),('validation',2),('test',2)]):return None,{'state':'insufficient_data','sequences':counts}
    def batch(ids):
        return [torch.from_numpy(np.stack(a)) for a in [[x[i-4:i] for i in ids],[mask[i-4:i] for i in ids],[x[i:i+1] for i in ids],[mask[i:i+1] for i in ids]]]
    train,val,test=[batch(splits[k]) for k in ['train','validation','test']]
    torch.manual_seed(42);model=DeepCTM(c);optimizer=torch.optim.Adam(model.parameters(),lr=c['learning_rate'],weight_decay=c['weight_decay']);best=math.inf;weights=None
    for epoch in range(epochs):
        model.train();optimizer.zero_grad();out=model(train[0],train[1],1);loss,_=model.loss(out,train[2],train[3]);loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),5);optimizer.step()
        model.eval()
        with torch.no_grad():
            pred=model(val[0],val[1],1)['prediction'];score=((pred-val[2])/model.scales).square()[val[3]].mean().item()
        if score<best:best=score;weights=copy.deepcopy(model.state_dict())
    model.load_state_dict(weights);model.eval()
    with torch.no_grad():
        out=model(test[0],test[1],1);pred=out['prediction'];persist=test[0][:,-1:];state=test[0][:,-1]/model.scales
        for i in range(1,model.n-1):state[:,i]=state[:,0]+(state[:,-1]-state[:,0])*i/(model.n-1)
        pure,_=model.physics(state);pure=pure[:,None]*model.scales
        def score(a):return {k:float((a-test[2])[test[3]][:,j].square().mean().sqrt()) for j,k in enumerate(['flow_rmse_veh_h','density_rmse_veh_km','speed_rmse_kmh'])}
        flows=torch.cat([out['flows'][...,:1],pred[...,0]],-1)
        mass=mass_error(out['previous'][...,1],pred[...,1],flows,model.lengths,1/60)
    report={'state':'trained_provisional','sequences':counts,'target_bins':splits,'deepctm':score(pred),'persistence':score(persist),'pure_ctm':score(pure),'mean_mass_discrepancy_vehicles':float(mass.mean()),'epochs':epochs}
    # Only display forecasts in untouched test period, using past observations.
    fields=[]
    with torch.no_grad():
        for i in splits['test']:
            out=model(torch.from_numpy(x[i-4:i][None]),torch.from_numpy(mask[i-4:i][None]),1)
            fields.append({'bin':i,'speed_kmh':out['prediction'][0,0,:,2].tolist()})
    return (model,fields),report


def tracers(fields,start,stations,lengths,direction):
    """Integrate dx/dt = predicted cell speed; stop at missing forecast or link end."""
    lookup={start+f['bin']*60:f['speed_kmh'] for f in fields};result=[]
    sign=1 if direction=='eastbound' else -1
    low,high=stations;origin=low+100 if sign==1 else high-100;finish=high-100 if sign==1 else low+100
    boundaries=np.cumsum(np.array(lengths)*1000)
    for t0 in sorted(lookup):
        for offset in [0,30]:
            t=t0+offset;pos=origin;points=[]
            for _ in range(1800):
                key=start+math.floor((t-start)/60)*60
                if key not in lookup:break
                distance=pos-(low-50) if sign==1 else high+50-pos
                cell=min(len(lengths)-1,int(np.searchsorted(boundaries,distance)))
                speed=lookup[key][cell]/3.6
                points.append([round(t,3),round(pos,2),round(speed,2)])
                pos+=sign*speed*2;t+=2
                if (sign==1 and pos>=finish) or (sign==-1 and pos<=finish):break
            if len(points)>1:result.append({'points':points})
    return result


def run(directory,epochs=20):
    torch.set_num_threads(1);directory=Path(directory);cfg=json.loads((directory/'config.json').read_text());manifest=json.loads((directory/'manifest.json').read_text());index=json.loads((directory/'figures/index.json').read_text())
    base=json.loads(Path('config/deepctm.json').read_text());base.update(interval_s=60,horizon_steps=1)
    start=math.ceil(manifest['start']/60)*60;end=math.floor(manifest['end']/60)*60;n=int((end-start)/60)
    output=directory/'virtual-model';output.mkdir(exist_ok=True);features=[];valid=[];quality=[]
    cache=output/'features.npz'
    if cache.exists():
        data=np.load(cache);features=data['features'];valid=data['valid']
    else:
        for i,site in enumerate(cfg['sites_west_to_east']):
            c={**base,'road_bearing_east_deg':cfg['road_bearings_deg'][i]}
            f,m,q=extract_site(events(directory,site),start,end,cfg['rotation_deg'][i],c);features.append(f);valid.append(m);quality.append(q)
            print(site,'valid minutes',m.sum(axis=0).tolist(),flush=True)
        np.savez_compressed(cache,features=np.array(features),valid=np.array(valid),start=start,interval_s=60);atomic(output/'quality.json',quality)
    result={'method':'Provisional DeepCTM adaptation, 60-second cells in time, four-minute context, one-minute forecast; virtual tracers are not vehicle predictions','start':start,'end':end,'links':[],'limitations':['Only untouched final 20% test windows are displayed; earlier times stay blank.','No measured intermediate trajectories exist; accuracy is assessed only at sensor endpoints.','One hour, approximate alignment, unknown clock offsets, no verified signals, turns or lateral inflows.','All vehicle classes pooled. Tracers have no object identity or class.','Shorter time step than the paper; not a reproduction of its 15/60-minute results.']}
    for i in range(len(index['sites'])-1):
        a,b=index['sites'][i:i+2];gap=b['station_m']-a['station_m'];virtual=max(1,math.ceil((gap-100)/150));lengths=[.1]+[(gap-100)/1000/virtual]*virtual+[.1]
        if gap<=100:continue
        for d,direction in enumerate(['eastbound','westbound']):
            c={**base,'cell_lengths_km':lengths if d==0 else lengths[::-1]};x=np.zeros((n,len(lengths),3),np.float32);mask=np.zeros((n,len(lengths)),bool)
            for node,j in zip([0,-1],[i,i+1] if d==0 else [i+1,i]):x[:,node]=features[j][:,d];mask[:,node]=valid[j][:,d]
            fitted,report=fit(x,mask,c,epochs);link={'sites':[a['site'],b['site']],'names':[a['name'],b['name']],'direction':direction,'report':report,'cell_lengths_km':c['cell_lengths_km'],'paths':[]}
            if fitted:
                model,fields=fitted;link['fields']=fields;link['paths']=tracers(fields,start,[a['station_m'],b['station_m']],c['cell_lengths_km'],direction)
                torch.save({'state_dict':model.state_dict(),'config':c},output/(a['site']+'-'+direction+'.pt'))
            result['links'].append(link);print(a['name'],b['name'],direction,report['state'],flush=True)
    atomic(directory/'figures/virtual-paths.json',result);atomic(output/'report.json',result)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--capture',required=True);p.add_argument('--epochs',type=int,default=20);a=p.parse_args();run(a.capture,a.epochs)
