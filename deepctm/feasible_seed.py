"""Experimental numerical initialization; no relaxation of physical constraints.

The min/max velocity envelopes respect both endpoint speeds and the same
discrete acceleration limits. A convex combination has the requested integral
and remains feasible. It supplies no identity or signal-state evidence.
"""
import numpy as np

def velocity_seed(a,b,t,vmax,amin,amax):
    t=np.asarray(t,float)-a['t'];duration=b['t']-a['t'];v0=a['v'];v1=b['v']
    if len(t)<3 or not np.all(np.isfinite(t)) or not np.all(np.diff(t)>0):return None
    if not np.all(np.isfinite([duration,v0,v1,a['x'],b['x'],vmax,amin,amax])):return None
    if duration<=0 or vmax<=0 or amin>=0 or amax<=0 or abs(t[0])>1e-8 or abs(t[-1]-duration)>1e-8:return None
    if not 0<=v0<=vmax or not 0<=v1<=vmax:return None
    lower=np.maximum.reduce([np.zeros_like(t),v0+amin*t,v1-amax*(duration-t)])
    upper=np.minimum.reduce([np.full_like(t,vmax),v0+amax*t,v1-amin*(duration-t)])
    if np.any(lower>upper+1e-9):return None
    integrate=lambda v:float(np.sum((v[1:]+v[:-1])*np.diff(t)/2))
    lo,hi=integrate(lower),integrate(upper);distance=b['x']-a['x']
    if distance<lo-1e-8 or distance>hi+1e-8:return None
    alpha=0. if hi-lo<1e-10 else np.clip((distance-lo)/(hi-lo),0,1)
    return lower+alpha*(upper-lower)

def retry(a,b,reference,params,smoothness=.01):
    from .trajectory_reconstruction import refine
    options=dict(**params,smoothness=smoothness,position_tolerance=0,speed_tolerance=0)
    first=refine(a,b,reference,**options)
    if first['state']=='candidate':return first,False
    second=refine(a,b,reference,**options,feasible_initialization=True)
    return second,second['state']=='candidate'
