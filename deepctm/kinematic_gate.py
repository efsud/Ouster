"""Experimental exact feasible-velocity gate, not a displayed prediction.

Removes the legacy cubic's arbitrary acceleration rejection. Final trajectory
refinement and identity competition still apply; no bounds are relaxed.
"""
import numpy as np
from .trajectory_reconstruction import grid,integrate_matrix
from .feasible_seed import velocity_seed

def path(a,b,params):
    sign=1 if b['x']>a['x'] else -1
    aa=dict(a,x=a['x']*sign,v=a['v']*sign)
    bb=dict(b,x=b['x']*sign,v=b['v']*sign)
    if not 0<bb['t']-aa['t']<=120:return None
    t=grid(aa,bb)
    v=velocity_seed(aa,bb,t,**params)
    if v is None:return None
    A,_=integrate_matrix(t)
    return np.column_stack([t,(aa['x']+A@v)*sign,v]).tolist()
