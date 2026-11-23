"""Components of the supplied Florida Word recommendation (not a neural model).

All positions increase downstream. Hidden truth is never an estimator argument.
Unavailable priors remain explicit; a kinematic ablation is not full M3/M4.
"""
import math
import numpy as np
from scipy.optimize import Bounds, LinearConstraint, minimize


def grid(a,b,step=.5):
    duration=b['t']-a['t']
    if not 0<duration<=120:raise ValueError('Gap must be within (0,120] seconds')
    return np.linspace(a['t'],b['t'],max(2,math.ceil(duration/step))+1)


def baseline(a,b,kind='hermite',step=.5):
    t=grid(a,b,step);d=b['t']-a['t'];u=(t-a['t'])/d
    if kind=='linear':
        x=a['x']+(b['x']-a['x'])*u;v=np.full_like(t,(b['x']-a['x'])/d)
    elif kind=='hermite':
        x=(2*u**3-3*u*u+1)*a['x']+(u**3-2*u*u+u)*d*a['v']+(-2*u**3+3*u*u)*b['x']+(u**3-u*u)*d*b['v']
        v=((6*u*u-6*u)*a['x']+(3*u*u-4*u+1)*d*a['v']+(-6*u*u+6*u)*b['x']+(3*u*u-2*u)*d*b['v'])/d
    else:raise ValueError('Unknown baseline')
    return np.column_stack([t,x,v])


def newell(a,b,leader,tau,spacing,desired_speed,following_verified=False,following_estimated=False):
    """x_f(t)=min(free trajectory, x_leader(t-tau)-spacing).

    A numerical same-lane test is not controller/scene verification. Caller must
    explicitly supply supported following metadata. No hidden-tail extrapolation.
    """
    if not following_verified and not following_estimated:return {'state':'unavailable','reason':'leader_lane_relationship_unverified'}
    if tau<=0 or spacing<=0 or desired_speed<=0:raise ValueError('Positive Newell parameters required')
    leader=np.asarray(leader,float);t=grid(a,b)
    if len(leader)<2 or np.any(np.diff(leader[:,0])<=0) or np.any(np.diff(leader[:,0])>1.5):
        return {'state':'unavailable','reason':'leader_discontinuous'}
    shifted=t-tau
    if shifted[0]<leader[0,0] or shifted[-1]>leader[-1,0]:return {'state':'unavailable','reason':'leader_coverage_missing'}
    reference=np.interp(shifted,leader[:,0],leader[:,1])-spacing
    x=np.minimum(a['x']+desired_speed*(t-a['t']),reference)
    if abs(x[0]-a['x'])>2 or np.any(np.diff(x)<-1e-6):return {'state':'infeasible','reason':'leader_boundary_conflict'}
    v=np.gradient(x,t)
    return {'state':'candidate','points':np.column_stack([t,x,v]),'endpoint_error_m':float(x[-1]-b['x']),'source':'Newell leader translation',
            'following_evidence':'verified' if following_verified else 'estimated_not_lane_verified'}


def integrate_matrix(t):
    """Trapezoidal velocity integration is exact for constant interval acceleration."""
    n=len(t);A=np.zeros((n,n));D=np.zeros((n-1,n))
    for i,dt in enumerate(np.diff(t)):
        A[i+1]=A[i];A[i+1,i]+=dt/2;A[i+1,i+1]+=dt/2
        D[i,i]=-1/dt;D[i,i+1]=1/dt
    return A,D


def refine(a,b,reference,vmax=30.,amin=-4.,amax=3.,smoothness=.1,
           position_tolerance=1.,speed_tolerance=1.,leader_ceiling=None,
           ctm_speed_envelope=None,red_position_ceiling=None):
    """Constrained kinematic refinement. Missing priors are explicit ablations.

    Optional ceiling arrays are [time, maximum_position]. Caller may supply red
    ceilings only for a verified no-crossing interval before an allowed release.
    CTM envelope [time, lower_speed, upper_speed] is a soft penalty, not truth.
    """
    reference=np.asarray(reference,float);t=grid(a,b)
    if not np.all(np.isfinite(reference)) or vmax<=0 or amin>=0 or amax<=0:raise ValueError('Invalid optimization inputs')
    A,D=integrate_matrix(t);target=np.interp(t,reference[:,0],reference[:,1])-a['x'];scale=max(10.,abs(b['x']-a['x']))
    speed_target=np.interp(t,reference[:,0],reference[:,2]);n=len(t)
    lower=np.zeros(n);upper=np.full(n,vmax,dtype=float)
    for i,ep in [(0,a),(-1,b)]:lower[i]=max(0.,ep['v']-speed_tolerance);upper[i]=min(vmax,ep['v']+speed_tolerance)
    if np.any(lower>upper):return {'state':'infeasible','reason':'endpoint_speed_out_of_bounds'}
    constraints=[LinearConstraint(D,amin,amax),LinearConstraint(A[-1:],b['x']-a['x']-position_tolerance,b['x']-a['x']+position_tolerance)]
    flags=[]
    for name,ceiling in [('leader_spacing',leader_ceiling),('red_crossing',red_position_ceiling)]:
        if ceiling is None:flags.append(name+'_unavailable');continue
        cap=np.asarray(ceiling,float);valid=(t>=cap[0,0])&(t<=cap[-1,0]);ceil=np.interp(t[valid],cap[:,0],cap[:,1])-a['x']
        constraints.append(LinearConstraint(A[valid],-np.inf,ceil))
    J=np.diff(D,axis=0) if len(D)>1 else np.zeros((0,n))
    envelope=None
    if ctm_speed_envelope is None:flags.append('ctm_envelope_unavailable')
    else:
        env=np.asarray(ctm_speed_envelope,float)
        if env[0,0]>t[0] or env[-1,0]<t[-1] or np.any(env[:,1]>env[:,2]):raise ValueError('Invalid CTM envelope coverage')
        envelope=(np.interp(t,env[:,0],env[:,1]),np.interp(t,env[:,0],env[:,2]))
    def objective(v):
        err=(A@v-target)/scale;dv=(v-speed_target)/max(vmax,1);jerk=J@v
        loss=err@err/n+.05*(dv@dv)/n+smoothness*(jerk@jerk)/max(1,len(jerk))
        grad=2*A.T@err/(scale*n)+.1*dv/(max(vmax,1)*n)+2*smoothness*J.T@jerk/max(1,len(jerk))
        if envelope is not None:
            delta=np.minimum(v-envelope[0],0)+np.maximum(v-envelope[1],0)
            loss+=.2*(delta@delta)/(vmax*vmax*n);grad+=.4*delta/(vmax*vmax*n)
        return loss,grad
    result=minimize(objective,np.clip(speed_target,lower,upper),jac=True,method='SLSQP',bounds=Bounds(lower,upper),constraints=constraints,options={'maxiter':150,'ftol':1e-8})
    v=result.x;x=a['x']+A@v;acc=D@v
    violations=[]
    if np.min(v)<-1e-5 or np.max(v)>vmax+1e-5:violations.append('speed')
    if np.min(acc)<amin-1e-5 or np.max(acc)>amax+1e-5:violations.append('acceleration')
    if abs(x[-1]-b['x'])>position_tolerance+1e-5:violations.append('endpoint')
    for constraint in constraints:
        z=constraint.A@v
        if np.any(z<np.asarray(constraint.lb)-1e-5) or np.any(z>np.asarray(constraint.ub)+1e-5):violations.append('linear_constraint')
    if not result.success or violations:return {'state':'infeasible','reason':'optimization_failed','violations':violations,'solver':result.message}
    return {'state':'candidate','points':np.column_stack([t,x,v]),'acceleration':acc,'source':'bounded kinematic refinement','unavailable_constraints':flags,'violations':[],
            'endpoint_error_m':float(x[-1]-b['x']),'objective':float(result.fun)}
