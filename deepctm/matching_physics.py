"""Exact discrete kinematic reachability before identity competition.

This is a physical gate, not an identity score. Bounds are the same frozen
limits as final refinement; no widening, extrapolation or phase assumptions.
"""
import numpy as np
from .trajectory_reconstruction import grid

def reachability(a,b,params,max_duration=120):
    sign=1 if b['x']>=a['x'] else -1
    aa=dict(a,x=a['x']*sign,v=a['v']*sign);bb=dict(b,x=b['x']*sign,v=b['v']*sign)
    if not 0<bb['t']-aa['t']<=max_duration:return 'time_bound'
    vmax=params['vmax'];lo=params['amin'];hi=params['amax'];v0=aa['v'];v1=bb['v']
    if not all(np.isfinite(v) for ep in (aa,bb) for v in (ep['t'],ep['x'],ep['v'])):return 'nonfinite'
    if not 0<=v0<=vmax or not 0<=v1<=vmax:return 'endpoint_speed_bound'
    t=grid(aa,bb,max_duration=max_duration)-aa['t'];T=t[-1]
    lower=np.maximum.reduce([np.zeros_like(t),v0+lo*t,v1-hi*(T-t)])
    upper=np.minimum.reduce([np.full_like(t,vmax),v0+hi*t,v1-lo*(T-t)])
    if np.any(lower>upper+1e-8):return 'endpoint_acceleration_bound'
    minimum=float(np.sum((lower[1:]+lower[:-1])*np.diff(t)/2));maximum=float(np.sum((upper[1:]+upper[:-1])*np.diff(t)/2));dx=bb['x']-aa['x']
    if dx<minimum-1e-6:return 'too_little_distance_for_endpoint_speeds'
    if dx>maximum+1e-6:return 'too_much_distance_for_available_time'
    return None

def associate(left,right,params,max_distance=350):
    from .spatial_bridges import associate_residual
    return associate_residual(left,right,threshold=1.5,margin=.25,max_rounds=1,
                              edge_filter=lambda a,b:reachability(a,b,params) is None,max_distance=max_distance)
