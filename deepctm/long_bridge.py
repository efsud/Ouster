"""Opt-in long-link physics, separate from the deployed 120-second identity gate."""
from .trajectory_reconstruction import baseline,refine
from .matching_physics import reachability

def prediction(a,b,params,max_duration=300):
    if not 120<b['t']-a['t']<=max_duration:return None
    if reachability(a,b,params,max_duration=max_duration) is not None:return None
    sign=1 if b['x']>=a['x'] else -1
    aa=dict(a,x=a['x']*sign,v=a['v']*sign);bb=dict(b,x=b['x']*sign,v=b['v']*sign)
    reference=baseline(aa,bb,max_duration=max_duration)
    result=refine(aa,bb,reference,**params,smoothness=.01,position_tolerance=0,speed_tolerance=0,max_duration=max_duration)
    if result['state']!='candidate':return None
    points=result['points'];points[:,1]*=sign
    return points
