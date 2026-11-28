"""Unpublished endpoint-envelope grid experiment; physical bounds unchanged.

Trapezoidal integration of piecewise linear velocity is exact only when its
kinks are represented. Add the kinks of the endpoint-reachable lower/upper
velocity envelopes, rather than weakening endpoint or acceleration constraints.
"""
import numpy as np
from .trajectory_reconstruction import grid, baseline, refine


def envelope_grid(a,b,params):
    duration=b['t']-a['t'];base=grid(a,b)-a['t']
    v0,v1=a['v'],b['v'];amin,amax=params['amin'],params['amax']
    # Each tuple is (slope, intercept) in elapsed time.
    lower=[(0.,0.),(amin,v0),(amax,v1-amax*duration)]
    upper=[(0.,params['vmax']),(amax,v0),(amin,v1-amin*duration)]
    extra=[]
    for lines in (lower,upper):
        for i,(s,c) in enumerate(lines):
            for z,d in lines[i+1:]:
                if abs(s-z)<1e-12:continue
                t=(d-c)/(s-z)
                if 1e-5<t<duration-1e-5:extra.append(t)
    points=sorted([*base,*extra]);chosen=[points[0]]
    for t in points[1:]:
        if t-chosen[-1]>1e-5:chosen.append(t)
    chosen[-1]=duration
    return np.asarray(chosen)+a['t']


def retry(a,b,params):
    reference=baseline(a,b)
    options=dict(**params,smoothness=.01,position_tolerance=0,speed_tolerance=0)
    first=refine(a,b,reference,**options)
    if first['state']=='candidate':return first,False
    if min(a['v'],b['v'])<0:return first,False
    t=envelope_grid(a,b,params)
    second=refine(a,b,reference,**options,time_grid=t,feasible_initialization=True)
    return second,second['state']=='candidate'
