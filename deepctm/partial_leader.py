"""Experimental partial Newell context; observed support only, no extrapolation.

The lateral proximity test is not a verified lane assignment. Context is a soft
reference and is withheld when two possible leaders are similarly close.
"""
import numpy as np
from .integrated_reconstruction import context,observed_at
from .trajectory_reconstruction import baseline,refine

def reference(site,target,a,b,params,tau=1.,weight=.5):
    ref=baseline(a,b);others,_,_=context(site,target,a,b);choices=[]
    for p in others:
        if np.any(np.diff(p[:,0])<=0) or np.any(np.diff(p[:,0])>1.5):continue
        at=observed_at(p,a['t']-tau)
        if at is None or not 2<=at-a['x']<=30:continue
        valid=(ref[:,0]-tau>=p[0,0])&(ref[:,0]-tau<=p[-1,0])
        supported=ref[valid,0]
        if len(supported)<3 or supported[-1]-supported[0]<5:continue
        spacing=at-a['x']
        x=np.interp(supported-tau,p[:,0],p[:,1])-spacing
        if np.any(np.diff(x)<-.1) or x[-1]>b['x']+30:continue
        choices.append((spacing,p,valid,x))
    choices.sort(key=lambda row:row[0])
    if not choices or len(choices)>1 and choices[1][0]-choices[0][0]<3:
        return ref,{'used':False,'reason':'no_unambiguous_supported_partial_leader'}
    spacing,p,valid,x=choices[0];support_t=ref[valid,0]
    # Fade to the endpoint-only reference before observed leader coverage ends.
    # No leader positions are extrapolated into the uncovered part of the gap.
    taper=np.minimum(1.,np.maximum(0.,(support_t[-1]-support_t)/2))
    ref[valid,1]=(1-weight*taper)*ref[valid,1]+weight*taper*x
    ref[:,2]=np.gradient(ref[:,1],ref[:,0]);ref[0,2]=a['v'];ref[-1,2]=b['v']
    ref[0,1]=a['x'];ref[-1,1]=b['x']
    return ref,{'used':True,'support_s':float(support_t[-1]-support_t[0]),'spacing_m':float(spacing),'tau_s':tau,
                'evidence':'estimated lateral proximity; lane relationship unverified'}

def reconstruct(site,target,a,b,params,solver_maxiter=600):
    ref,evidence=reference(site,target,a,b,params)
    result=refine(a,b,ref,**params,smoothness=.01,position_tolerance=0,speed_tolerance=0,solver_maxiter=solver_maxiter)
    return dict(result,partial_leader=evidence)
