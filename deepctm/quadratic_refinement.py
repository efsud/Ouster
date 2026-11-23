"""Experimental OSQP form of the existing kinematic objective.

No motion bound, endpoint tolerance, leader or signal permission is relaxed.
Only the kinematic ablation is implemented here. Production remains unchanged.
Reference: https://osqp.org/docs/interfaces/python.html
"""
import numpy as np
from scipy import sparse
from .trajectory_reconstruction import grid,integrate_matrix,baseline
from .feasible_seed import velocity_seed

def terms(a,b,reference,params,t,smoothness=.01):
    A,D=integrate_matrix(t);n=len(t);J=np.diff(D,axis=0)
    scale=max(10.,abs(b['x']-a['x']));vmax=params['vmax']
    target=np.interp(t,reference[:,0],reference[:,1])-a['x']
    speed=np.interp(t,reference[:,0],reference[:,2])
    P=2*(A.T@A/(scale*scale*n)+.05*np.eye(n)/(vmax*vmax*n)+smoothness*(J.T@J)/max(1,len(J)))
    q=-2*A.T@target/(scale*scale*n)-.1*speed/(vmax*vmax*n)
    return P,q,A,D

def solve(a,b,params,adaptive=False):
    import osqp
    if not np.all(np.isfinite([a[k] for k in ('t','x','v')]+[b[k] for k in ('t','x','v')])):
        return {'state':'infeasible','reason':'nonfinite_endpoint'}
    if not 0<b['t']-a['t']<=120:return {'state':'infeasible','reason':'duration'}
    if not 0<=min(a['v'],b['v']) or max(a['v'],b['v'])>params['vmax']:
        return {'state':'infeasible','reason':'endpoint_speed_out_of_bounds'}
    t=grid(a,b)
    if adaptive:
        from .adaptive_endpoint_grid import envelope_grid
        t=envelope_grid(a,b,params)
    seed=velocity_seed(a,b,t,**params)
    if seed is None:return {'state':'infeasible','reason':'kinematic_envelope'}
    reference=baseline(a,b);P,q,A,D=terms(a,b,reference,params,t);n=len(t)
    lo=np.zeros(n);hi=np.full(n,params['vmax']);lo[0]=hi[0]=a['v'];lo[-1]=hi[-1]=b['v']
    constraint=sparse.vstack([sparse.eye(n),sparse.csc_matrix(D),sparse.csc_matrix(A[-1:])],format='csc')
    lower=np.r_[lo,np.full(n-1,params['amin']),b['x']-a['x']]
    upper=np.r_[hi,np.full(n-1,params['amax']),b['x']-a['x']]
    model=osqp.OSQP();model.setup(P=sparse.csc_matrix(P),q=q,A=constraint,l=lower,u=upper,
        verbose=False,eps_abs=1e-8,eps_rel=1e-8,max_iter=50000,polishing=True,
        adaptive_rho_interval=50,time_limit=1.)
    model.warm_start(x=seed);result=model.solve(raise_error=False)
    if result.info.status_val!=1:return {'state':'infeasible','reason':'solver_not_solved','solver':result.info.status}
    v=result.x;z=constraint@v
    if not np.all(np.isfinite(v)) or np.any(z<lower-1e-5) or np.any(z>upper+1e-5):
        return {'state':'infeasible','reason':'constraint_check'}
    return {'state':'candidate','points':np.column_stack([t,a['x']+A@v,v]),
        'source':'experimental OSQP kinematic refinement','adaptive_grid':adaptive,
        'solver_iterations':int(result.info.iter),'solver_seconds':float(result.info.run_time),
        'violations':[],'unavailable_constraints':['leader_spacing','red_crossing','ctm_envelope']}
