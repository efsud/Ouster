"""Unpublished stationary latent-position estimate under bounded endpoint noise.

This deliberately does not claim exact endpoint interpolation. Observed points
remain unchanged, and residuals (at most 5 cm) are explicit. Never use for an
unverified identity or between-sensor association.
"""
import numpy as np
from .trajectory_reconstruction import grid

def estimate(a,b,same_identity=False):
    if not same_identity:return {'state':'unavailable','reason':'same_identity_required'}
    if not 1.5<b['t']-a['t']<=30:return {'state':'unavailable','reason':'duration'}
    if not np.all(np.isfinite([a[k] for k in ('t','x','v')]+[b[k] for k in ('t','x','v')])):
        return {'state':'unavailable','reason':'invalid_endpoint'}
    if abs(b['x']-a['x'])>.1:return {'state':'unavailable','reason':'position_displacement'}
    for ep in (a,b):
        e=ep.get('velocity_evidence',{})
        if not all(np.isfinite(e.get(k,np.nan)) for k in ('span_m','duration_s','trend_speed_mps','max_step_speed_mps','samples')):
            return {'state':'unavailable','reason':'missing_visible_context'}
        if abs(ep['v'])>.1 or e['samples']<5 or e['duration_s']<1 or e['span_m']>.1 or abs(e['trend_speed_mps'])>.05 or e['max_step_speed_mps']>.5:
            return {'state':'unavailable','reason':'visible_context_not_stationary'}
    t=grid(a,b);center=(a['x']+b['x'])/2
    return {'state':'candidate','points':np.column_stack([t,np.full(len(t),center),np.zeros(len(t))]),
        'method':'bounded_stationary_latent_position','endpoint_position_residual_m':[a['x']-center,b['x']-center],
        'observed_endpoint_speeds_mps':[a['v'],b['v']],'estimated_speed_mps':0.,
        'uncertainty':'bounded heuristic; not field-calibrated','exact_endpoint_interpolation':False}
