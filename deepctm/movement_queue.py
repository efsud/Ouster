"""Movement-group CTM prior for trajectory reconstruction.

SI units: density veh/m across the declared lane group; rates veh/s.
Unverified signals never create a hard permission or an invented schedule.
"""
import math
import numpy as np


def simulate(initial_density,lengths,dt,vf,w,jam,demand,downstream_supply,
             signal_permissions=None,signal_verified=False,side_arrivals=None,
             side_departures=None,estimated_capacity_factors=None):
    lengths=np.asarray(lengths,float);k=np.asarray(initial_density,float).copy()
    demand=np.asarray(demand,float);supply=np.asarray(downstream_supply,float)
    if dt<=0 or min(vf,w,jam)<=0 or np.any(lengths<=0) or len(k)!=len(lengths):raise ValueError('Invalid physical dimensions')
    if len(supply)!=len(demand) or np.any(demand<0) or np.any(supply<0):raise ValueError('Boundary rates must be nonnegative and aligned')
    if np.any(k<0) or np.any(k>jam):raise ValueError('Initial density outside storage bounds')
    if signal_permissions is not None and not signal_verified:return {'state':'unavailable','reason':'signal_permissions_unverified'}
    permission=np.ones(len(demand)) if signal_permissions is None else np.asarray(signal_permissions,float)
    factors=np.ones((len(demand),len(k)+1)) if estimated_capacity_factors is None else np.asarray(estimated_capacity_factors,float)
    if factors.shape!=(len(demand),len(k)+1) or not np.isfinite(factors).all() or np.any((factors<0)|(factors>1)):
        raise ValueError('Invalid estimated internal capacity factors')
    if permission.shape!=demand.shape or np.any((permission<0)|(permission>1)):raise ValueError('Invalid permission series')
    side_in=np.zeros((len(demand),len(k))) if side_arrivals is None else np.asarray(side_arrivals,float)
    side_out=np.zeros_like(side_in) if side_departures is None else np.asarray(side_departures,float)
    if side_in.shape!=(len(demand),len(k)) or side_out.shape!=side_in.shape or np.any(side_in<0) or np.any(side_out<0):raise ValueError('Invalid side movement rates')
    substeps=max(1,math.ceil(dt*max(vf,w)/float(lengths.min())));h=dt/substeps;capacity=vf*w*jam/(vf+w)
    densities=[k.copy()];flows=[];speeds=[];mass_errors=[];unserved_in=[];unserved_out=[]
    for t in range(len(demand)):
        total=np.zeros(len(k)+1);lateral_in=np.zeros(len(k));lateral_out=np.zeros(len(k));miss_in=np.zeros(len(k));miss_out=np.zeros(len(k));previous=k.copy()
        for _ in range(substeps):
            send=np.minimum(vf*k,capacity);receive=np.minimum(w*(jam-k),capacity)
            f=np.r_[min(demand[t],receive[0]),np.minimum(send[:-1],receive[1:]),min(send[-1]*permission[t],supply[t])]
            f*=factors[t]
            # Shared storage/sending budgets also constrain lateral source/sink rates.
            incoming=f[:-1]*h;outgoing=f[1:]*h;cars=k*lengths
            leave=np.minimum(side_out[t]*h,np.maximum(0,np.minimum(cars,send*h)-outgoing))
            enter=np.minimum(side_in[t]*h,np.maximum(0,np.minimum(jam*lengths-cars,receive*h)-incoming))
            k=(cars+incoming-outgoing+enter-leave)/lengths
            if np.any(k<-1e-8) or np.any(k>jam+1e-8):raise ArithmeticError('Storage constraint violated')
            total+=f*h;lateral_in+=enter;lateral_out+=leave;miss_in+=side_in[t]*h-enter;miss_out+=side_out[t]*h-leave
        error=(k-previous)*lengths-(total[:-1]-total[1:]+lateral_in-lateral_out)
        mass_errors.append(float(np.max(abs(error))));densities.append(k.copy());flows.append(total/dt)
        speeds.append(np.minimum(vf,np.divide(total[1:]/dt,k,out=np.full_like(k,vf),where=k>1e-8)))
        unserved_in.append(miss_in);unserved_out.append(miss_out)
    return dict(state='available',density=np.asarray(densities),flow=np.asarray(flows),speed=np.asarray(speeds),max_mass_error_vehicles=max(mass_errors,default=0.),
      unserved_side_arrivals=np.asarray(unserved_in),unserved_side_departures=np.asarray(unserved_out),
      signal_state='verified' if signal_permissions is not None else 'unavailable_no_signal_ablation',
      capacity_evidence='estimated_scenario_not_permission' if estimated_capacity_factors is not None else 'unmodified',
      caveats=['Aggregate speed is a soft prior, not an individual vehicle speed','Unserved side demand is reported, not silently inserted or carried across cells','External arrival demand not admitted must be handled by the caller reservoir'])
