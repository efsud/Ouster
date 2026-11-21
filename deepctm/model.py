"""Independent DeepCTM adaptation; see docs/deepctm.md and the Florida pair method notes."""
import math
import torch
from torch import nn


def ctm_step(density, demand, lengths, dt_hours=.25, v=50., w=18., jam=300., signal_mask=None, downstream_density=None):
    """Conservative open chain. k veh/km; boundary flows veh/h; lengths km.

    Substep by CFL. Return end density, time-averaged boundary flows, and q/k
    speed proxy. Optional signal masks and downstream supply are explicit; no lateral sources.
    """
    if dt_hours<=0 or v<=0 or w<=0 or jam<=0 or bool((lengths<=0).any()):raise ValueError('Positive physical parameters required')
    steps=math.ceil(dt_hours*max(v,w)/float(lengths.min()))
    dt=dt_hours/steps;cap=v*w*jam/(v+w)
    k=density;total=torch.zeros((*k.shape[:-1],k.shape[-1]+1),device=k.device,dtype=k.dtype)
    for _ in range(steps):
        send=torch.minimum(k*v,torch.full_like(k,cap))
        receive=torch.minimum((jam-k).clamp_min(0)*w,torch.full_like(k,cap))
        flow=torch.cat([torch.minimum(demand.clamp_min(0),receive[...,0]).unsqueeze(-1),torch.minimum(send[...,:-1],receive[...,1:]),send[...,-1:]],-1)
        if downstream_density is not None:
            tail=torch.minimum(flow[...,-1],((jam-downstream_density).clamp_min(0)*w).clamp_max(cap))
            flow=torch.cat([flow[...,:-1],tail.unsqueeze(-1)],-1)
        if signal_mask is not None:
            if bool(((signal_mask<0)|(signal_mask>1)).any()):raise ValueError('Signal mask must be between zero and one')
            flow=flow*signal_mask
        k=k+(flow[...,:-1]-flow[...,1:])*dt/lengths
        total=total+flow*dt
    flows=total/dt_hours
    speed=(flows[...,1:]/k.clamp_min(1e-6)).clamp(0,v)
    return k,flows,speed


def mass_error(previous, current, boundary_flows, lengths, dt_hours):
    return ((current-previous)*lengths-(boundary_flows[...,:-1]-boundary_flows[...,1:])*dt_hours).abs()


class DeepCTM(nn.Module):
    def __init__(self,config):
        super().__init__();self.config=config
        p=config['physical_dim'];f=config['free_dim'];n=len(config['cell_lengths_km'])
        self.register_buffer('lengths',torch.tensor(config['cell_lengths_km']))
        self.register_buffer('scales',torch.tensor([2000.,config['jam_density_veh_km'],config['free_speed_kmh']]))
        self.encoder=nn.Linear(3,p);self.free=nn.LSTMCell(3+p,f)
        self.forward_message=nn.Linear(p+f,p,bias=False);self.backward_message=nn.Linear(p+f,p,bias=False);self.self_message=nn.Linear(p+f,p)
        self.residual=nn.Linear(p,3);self.neural_head=nn.Linear(p+f,3)
        self.gate=nn.Linear(2*p+1,3);self.pec=nn.Sequential(nn.Linear(p+3,p),nn.Tanh(),nn.Linear(p,3))
        self.drop=nn.Dropout(config['dropout']);self.n=n

    def physics(self,state):
        c=self.config
        k,flows,v=ctm_step(state[...,1]*self.scales[1],state[...,0,0]*self.scales[0],self.lengths,c['interval_s']/3600,c['free_speed_kmh'],c['wave_speed_kmh'],c['jam_density_veh_km'])
        return torch.stack([flows[...,1:],k,v],-1)/self.scales,flows

    def forward(self,x,mask,horizon,feature_mask=None):
        """x [batch,context,nodes,3], mask [batch,context,nodes]. No future inputs."""
        batch=x.shape[0];c=self.config;state=x[:,0].clone()/self.scales
        initial_mask=mask[:,0,:,None].expand_as(state) if feature_mask is None else (feature_mask[:,0]&mask[:,0,:,None])
        prior=torch.zeros_like(state);prior[...,2]=1
        state=torch.where(initial_mask,state,prior)
        # Virtual initial state is interpolation, never a supervised label.
        for i in range(1,self.n-1):state[:,i]=state[:,0]+(state[:,-1]-state[:,0])*i/(self.n-1)
        h=torch.tanh(self.encoder(state));f=x.new_zeros(batch,self.n,c['free_dim']);cell=torch.zeros_like(f)
        outputs=[];physics=[];flows_list=[];previous=[];pec_terms=[]
        for t in range(x.shape[1]+horizon-1):
            if t<x.shape[1]:
                obs=x[:,t]/self.scales;valid=mask[:,t,:,None]
                observed=valid.expand_as(obs) if feature_mask is None else (feature_mask[:,t]&valid)
                error=self.pec(torch.cat([h,(state-obs)*observed],-1))
                target=(state.detach()-obs)
                pec_terms.append(((error-target).square()*observed).sum()/observed.sum().clamp_min(1))
                state=(state-c['pec_alpha']*error*observed).clamp_min(0)
                # Assimilation only at known context times; future rollout gets no observations.
                state=torch.where(observed,.5*obs+.5*state,state)
                state=torch.stack([state[...,0].clamp(0,3),state[...,1].clamp(0,1),state[...,2].clamp(0,1)],-1)
                h=torch.tanh(self.encoder(state))
            else:valid=torch.zeros_like(mask[:,0,:,None])
            old=state;phys,flows=self.physics(old)
            physical=(phys+.1*torch.tanh(self.residual(h))).clamp_min(0)
            hf=torch.cat([h,f],-1)
            upstream=torch.cat([torch.zeros_like(hf[:,:1]),hf[:,:-1]],1)
            downstream=torch.cat([hf[:,1:],torch.zeros_like(hf[:,:1])],1)
            message=torch.nn.functional.leaky_relu(self.forward_message(upstream)+self.backward_message(downstream)+self.self_message(hf))
            fin=torch.cat([state,h],-1).reshape(batch*self.n,-1)
            ff,cc=self.free(fin,(f.reshape(batch*self.n,-1),cell.reshape(batch*self.n,-1)))
            f=ff.reshape(batch,self.n,-1);cell=cc.reshape(batch,self.n,-1)
            neural=torch.sigmoid(self.neural_head(torch.cat([self.drop(message),f],-1)))
            g=torch.sigmoid(self.gate(torch.cat([message,self.encoder(physical),valid.to(x.dtype)],-1)))
            state=g*physical+(1-g)*neural
            state=torch.stack([state[...,0].clamp(0,3),state[...,1].clamp(0,1),state[...,2].clamp(0,1)],-1)
            h=torch.tanh(self.encoder(state))
            if t>=x.shape[1]-1:
                outputs.append(state*self.scales);physics.append(phys*self.scales);flows_list.append(flows);previous.append(old*self.scales)
        return {'prediction':torch.stack(outputs,1),'physics':torch.stack(physics,1),'flows':torch.stack(flows_list,1),'previous':torch.stack(previous,1),'pec':torch.stack(pec_terms).mean()}

    def loss(self,result,target,mask,feature_mask=None):
        valid=mask[...,None].expand_as(target) if feature_mask is None else (feature_mask&mask[...,None]);pred=result['prediction'];scale=self.scales
        loss_scale=pred.new_tensor(self.config.get('data_loss_scales',self.scales.tolist()))
        squared=((pred-target)/loss_scale).square()*valid
        if self.config.get('balanced_features',False):
            counts=valid.sum(dim=(0,1,2));available=counts>0
            mse=(squared.sum(dim=(0,1,2))/counts.clamp_min(1))[available].mean() if available.any() else squared.sum()*0
        else:mse=squared.sum()/valid.sum().clamp_min(1)
        phys=((pred-result['physics'])/scale).square().mean()
        smooth=((pred[:,:,1:]-pred[:,:,:-1])/scale).square().mean()
        terms=[mse,phys,smooth,result['pec']]
        return sum(w*t for w,t in zip(self.config['loss_weights'],terms)),terms
