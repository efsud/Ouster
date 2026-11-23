"""Experimental position-only white-jerk Kalman/RTS gap reference.

RTS recursion: Särkkä (2013), Bayesian Filtering and Smoothing, §8.2.
https://users.aalto.fi/~ssarkka/pub/cup_book_online_20131111.pdf
This is not CTM or signal evidence. Gaussian covariance is not field-calibrated
uncertainty. Only a reference for the unchanged bounded kinematic refinement.
"""
import numpy as np
from .trajectory_reconstruction import grid,refine

def dynamics(dt,q):
    F=np.array([[1,dt,dt*dt/2],[0,1,dt],[0,0,1]],float)
    Q=q*np.array([[dt**5/20,dt**4/8,dt**3/6],[dt**4/8,dt**3/3,dt*dt/2],[dt**3/6,dt*dt/2,dt]])
    return F,Q

def reference(before,after,a,b,q=.1,measurement_variance=.04):
    before=np.asarray(before,float)[:,:2];after=np.asarray(after,float)[:,:2]
    if q<=0 or measurement_variance<=0:raise ValueError('Positive noise scales required')
    if len(before)<5 or len(after)<5:raise ValueError('Both visible flanks required')
    if not np.all(np.isfinite(before)) or not np.all(np.isfinite(after)):raise ValueError('Invalid observations')
    if np.any(np.diff(before[:,0])<=0) or np.any(np.diff(after[:,0])<=0):raise ValueError('Unordered observations')
    if before[-1,0]>a['t']+1e-8 or after[0,0]<b['t']-1e-8:raise ValueError('Hidden gap observations are forbidden')
    t_gap=grid(a,b);observed={float(t):float(x) for t,x in np.vstack([before,after])}
    times=np.unique(np.r_[before[:,0],t_gap,after[:,0]])
    m=np.array([before[0,1],np.median(np.diff(before[:,1])/np.diff(before[:,0])),0.])
    P=np.diag([measurement_variance,25.,16.]);means=[];cov=[];pred=[];pred_cov=[];transitions=[]
    for i,t in enumerate(times):
        if i:
            F,Q=dynamics(t-times[i-1],q);m=F@m;P=F@P@F.T+Q
        else:F=np.eye(3)
        pred.append(m.copy());pred_cov.append(P.copy());transitions.append(F)
        if float(t) in observed:
            K=P[:,0]/(P[0,0]+measurement_variance);m=m+K*(observed[float(t)]-m[0])
            A=np.eye(3)-np.outer(K,[1.,0.,0.]);P=A@P@A.T+measurement_variance*np.outer(K,K)
        means.append(m.copy());cov.append((P+P.T)/2)
    sm=np.array(means);sc=np.array(cov)
    for i in range(len(times)-2,-1,-1):
        C=np.linalg.solve(pred_cov[i+1],transitions[i+1]@cov[i]).T
        sm[i]=means[i]+C@(sm[i+1]-pred[i+1]);sc[i]=cov[i]+C@(sc[i+1]-pred_cov[i+1])@C.T
    indices=np.searchsorted(times,t_gap)
    return np.column_stack([t_gap,sm[indices,0],sm[indices,1]])

def estimate(before,after,a,b,params,q=.1,measurement_variance=.04):
    ref=reference(before,after,a,b,q,measurement_variance)
    return refine(a,b,ref,**params,smoothness=.01,position_tolerance=0,speed_tolerance=0)

def hybrid(before,after,a,b,params,q,measurement_variance):
    """Preserve baseline availability; RTS is an optional reference, not evidence."""
    from .endpoint_speed import reconstruct
    base=reconstruct(a,b,params,None)
    if base['state']!='candidate':return dict(base,rts_used=False)
    candidate=estimate(before,after,a,b,params,q,measurement_variance)
    if candidate['state']!='candidate':return dict(base,rts_used=False)
    return dict(candidate,rts_used=True)
