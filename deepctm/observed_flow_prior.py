"""Experimental local observed-flow prior, not verified lane or signal evidence.

Only simultaneous, nearby, other-object observations constrain an inferred path.
The target's complete identity is excluded by context(). A full recording outage
therefore cannot create a fictitious observed velocity field inside that outage.
"""
import numpy as np
from collections import defaultdict
from .integrated_reconstruction import context
from .trajectory_reconstruction import baseline,refine

def envelope(site,target,a,b,params,reference=None,min_neighbors=2,radius_m=25):
    reference=baseline(a,b) if reference is None else reference
    identities=defaultdict(list)
    for tr in site['tracks']:identities[tuple(tr.get('source_key',[])[:2])].append(tr)
    others=[context(dict(site,tracks=tracks),target,a,b)[0] for tracks in identities.values()]
    vmax=params['vmax'];rows=[];supported=0
    for t,x,_ in reference:
        if t<=a['t'] or t>=b['t']:rows.append([t,0.,vmax]);continue
        velocities=[]
        for fragments in others:
            candidates=[]
            for p in fragments:
                i=int(np.searchsorted(p[:,0],t,side='right'))
                if not 0<i<len(p):continue
                dt=p[i,0]-p[i-1,0]
                if not .1<=dt<=1.5:continue
                xx=float(np.interp(t,p[i-1:i+1,0],p[i-1:i+1,1]));v=(p[i,1]-p[i-1,1])/dt
                if abs(xx-x)<=radius_m and 0<=v<=vmax:candidates.append(v)
            if len(candidates)==1:velocities.append(candidates[0])
        if len(velocities)<min_neighbors:rows.append([t,0.,vmax]);continue
        q25,q50,q75=np.quantile(velocities,[.25,.5,.75]);spread=max(1.,q75-q25)
        # Multimodal traffic offers no narrow aggregate prior.
        if q75-q25>5:rows.append([t,0.,vmax]);continue
        rows.append([t,max(0.,q50-spread),min(vmax,q50+spread)]);supported+=1
    return np.asarray(rows),{'supported_samples':supported,'samples':len(reference),'minimum_other_objects':min_neighbors,
                             'radius_m':radius_m,'lane_relationship':'estimated_not_verified'}

def reconstruct(site,target,a,b,params):
    ref=baseline(a,b);env,evidence=envelope(site,target,a,b,params,ref)
    result=refine(a,b,ref,**params,smoothness=.01,position_tolerance=0,speed_tolerance=0,
                  ctm_speed_envelope=env if evidence['supported_samples'] else None,solver_maxiter=600)
    return dict(result,observed_flow_prior=evidence)
