"""Experimental Newell + CTM + estimated signal soft-prior reconstruction.

All context excludes the target's complete ID. No masked truth enters this API.
Provisional lane/stop-line geometry is an assumption, never a hard signal rule.
"""
import numpy as np
from .trajectory_reconstruction import baseline,newell,refine,grid
from .movement_queue import simulate


def observed_at(points,t):
    p=np.asarray(points,float)
    if len(p)<2 or t<p[0,0] or t>p[-1,0]:return None
    i=np.searchsorted(p[:,0],t,side='right')
    if i==len(p):return p[-1,1]
    if i==0 or p[i,0]-p[i-1,0]>1.5:return None
    return float(np.interp(t,p[:,0],p[:,1]))


def context(site,target,a,b):
    sign=1 if target['direction']=='eastbound' else -1
    identity=target['source_key'][:2];center=sign*site['station_m']
    lateral=target.get('lateral_start_m')
    if lateral is None:return [],None,center
    others=[]
    for tr in site['tracks']:
        if tr['source_key'][:2]==identity or tr['source_key'][0]!=target['source_key'][0]:continue
        if tr['class_type']!='2' or tr['direction']!=target['direction']:continue
        if any(abs(tr.get(k,1e6)-lateral)>1.25 for k in ('lateral_start_m','lateral_end_m')):continue
        p=np.asarray(tr['points'],float).copy();p[:,1]*=sign
        others.append(p)
    leaders=[]
    for p in others:
        if np.any(np.diff(p[:,0])<=0) or np.any(np.diff(p[:,0])>1.5):continue
        x=observed_at(p,a['t']-1);end=observed_at(p,b['t'])
        if x is not None and end is not None and 2<=x-a['x']<=30 and end>=b['x']+2:
            leaders.append((x-a['x'],p))
    leaders.sort(key=lambda item:item[0])
    # Close parallel candidates are not an unambiguous lane leader.
    leader=leaders[0] if leaders and (len(leaders)==1 or leaders[1][0]-leaders[0][0]>=3) else None
    return others,leader,center


def reconstruct(site,target,a,b,params,signal=None,mode='integrated',weight=.5):
    """a,b already downstream-oriented. signal = [t, capacity factor], estimated.

    CTM initial density and inflow use only other vehicles before the gap. Leader
    observations during it are allowed for local occlusion, not a total outage.
    """
    reference=baseline(a,b);others,leader,center=context(site,target,a,b)
    flags=[];leader_used=False;envelope=None;mass=None
    if mode in ('newell','integrated'):
        if leader is not None:
            spacing,p=leader
            candidate=newell(a,b,p,1.,spacing,params['vmax'],following_estimated=True)
            if candidate['state']=='candidate':
                reference[:,1:]=(1-weight)*reference[:,1:]+weight*candidate['points'][:,1:];leader_used=True
        if not leader_used:flags.append('estimated_leader_unavailable')
    if mode in ('ctm','integrated'):
        t=grid(a,b);dt=float(t[1]-t[0]);lengths=np.full(12,20.);density=np.zeros(12)
        for p in others:
            # Initialize from observations at/before the gap, not interpolation
            # requiring a future observation hidden by the outage experiment.
            prior=p[p[:,0]<=a['t']]
            x=float(prior[-1,1]) if len(prior) and a['t']-prior[-1,0]<=1.5 else None
            if x is not None and -120<=x-center<120:density[int((x-center+120)//20)]+=1/20
        # Fragment counts at the observed upstream boundary, preceding 30 s only.
        entries=sum(a['t']-30<=p[0,0]<a['t'] and -120<=p[0,1]-center<-90 for p in others)
        vf=params['vmax'];w=5.;jam=.2;cap=vf*w*jam/(vf+w)
        factors=None
        if signal is not None:
            sg=np.asarray(signal,float)
            if sg[0,0]<=t[0] and sg[-1,0]>=t[-1]:
                factors=np.ones((len(t)-1,13));factors[:,6]=np.interp(t[:-1],sg[:,0],sg[:,1])
            else:flags.append('signal_coverage_unavailable')
        else:flags.append('signal_mapping_unavailable')
        r=simulate(np.minimum(density,jam),lengths,dt,vf,w,jam,
                   np.full(len(t)-1,entries/30),np.full(len(t)-1,cap),estimated_capacity_factors=factors)
        # Probe the aggregate field along the reference; never force a vehicle
        # to equal a cell mean. Out-of-ROI sections get no speed restriction.
        speeds=[]
        for i,x in enumerate(reference[:,1]):
            cell=int((x-center+120)//20)
            speeds.append(r['speed'][min(i,len(t)-2),cell] if 0<=cell<12 else vf)
        speeds=np.array(speeds);envelope=np.column_stack([t,np.maximum(0,speeds-5),np.minimum(vf,speeds+5)])
        mass=r['max_mass_error_vehicles']
    result=refine(a,b,reference,**params,smoothness=.01,ctm_speed_envelope=envelope,position_tolerance=0,speed_tolerance=0)
    result.update(leader_used=leader_used,ctm_used=envelope is not None,signal_used=mode in ('ctm','integrated') and signal is not None and 'signal_coverage_unavailable' not in flags,
                  max_mass_error=mass,flags=flags,estimated_priors=True)
    return result
