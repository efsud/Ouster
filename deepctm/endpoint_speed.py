"""Conservative stationary-endpoint correction from visible samples only.

Recorded positions/speeds are never edited. Only an inferred gap may replace a
small negative derivative with zero when a quiet, compact observed context
supports a stationary endpoint. Sustained reverse motion remains unavailable.
"""
import numpy as np

def evidence(points):
    p=np.asarray([[row[0],row[1]] for row in points],float)
    if len(p)<5 or not np.all(np.isfinite(p)):return None
    dt=np.diff(p[:,0]);dx=np.diff(p[:,1])
    if np.any(dt<=0) or np.any(dt>1.5) or p[-1,0]-p[0,0]<1:return None
    return dict(span_m=float(np.ptp(p[:,1])),duration_s=float(p[-1,0]-p[0,0]),
                trend_speed_mps=float((p[-1,1]-p[0,1])/(p[-1,0]-p[0,0])),
                max_step_speed_mps=float(np.max(abs(dx/dt))),samples=len(p))

def orient(endpoint,sign):
    ep=dict(endpoint,x=endpoint['x']*sign,v=endpoint['v']*sign)
    if endpoint.get('velocity_evidence'):
        ep['velocity_evidence']=dict(endpoint['velocity_evidence'],trend_speed_mps=endpoint['velocity_evidence']['trend_speed_mps']*sign)
    return ep

def correct(endpoint,config):
    """Return unchanged positive speed; only correct supported near-zero noise."""
    v=endpoint['v'];e=endpoint.get('velocity_evidence')
    if v>=0:return dict(endpoint),None
    if not e:return None,'missing_visible_speed_evidence'
    limit=config['negative_speed_limit_mps'];span=config['position_span_limit_m']
    if not np.isfinite(v) or not -limit<=v<0:return None,'reverse_speed_exceeds_noise_limit'
    if not all(np.isfinite(e.get(k,np.nan)) for k in ('span_m','trend_speed_mps','max_step_speed_mps','duration_s')):return None,'invalid_speed_evidence'
    if e['samples']<5 or e['duration_s']<1:return None,'insufficient_visible_context'
    # Require mixed signs or an effectively stationary trend. Do not flatten a
    # sustained backwards trend even when its magnitude is below the speed gate.
    if e['span_m']>span or abs(e['trend_speed_mps'])>config['trend_limit_mps'] or e['max_step_speed_mps']>config['step_speed_limit_mps']:
        return None,'visible_motion_not_stationary'
    return dict(endpoint,v=0.),dict(observed_speed_mps=float(v),estimated_speed_mps=0.,evidence=e,reason='estimated_stationary_endpoint')

def reconstruct(a,b,params,config,smoothness=.01):
    from .trajectory_reconstruction import baseline,refine
    def solve(aa,bb):
        return refine(aa,bb,baseline(aa,bb),**params,smoothness=smoothness,position_tolerance=0,speed_tolerance=0)
    strict=solve(a,b)
    if strict['state']=='candidate' or config is None:return dict(strict,endpoint_corrections=[],endpoint_policy='strict')
    aa,ca=correct(a,config);bb,cb=correct(b,config)
    if aa is None or bb is None:return dict(strict,endpoint_corrections=[],correction_rejection=[ca if aa is None else None,cb if bb is None else None])
    changes=[dict(endpoint=key,**c) for key,c in [('start',ca),('end',cb)] if c is not None]
    if not changes:return dict(strict,endpoint_corrections=[])
    result=solve(aa,bb)
    return dict(result,endpoint_corrections=changes,endpoint_policy='stationary_noise_correction_v1')
