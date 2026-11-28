"""Experimental same-ID lateral motion gate; not cross-ID or lane matching."""
import numpy as np
from .spatial_bridges import endpoint

def lateral_curve(before,after,times):
    a=endpoint(before.get('lateral_end_context',[]),True)
    b=endpoint(after.get('lateral_start_context',[]),False)
    if a is None or b is None:return None,{'reason':'lateral_context_missing'}
    dt=b['t']-a['t'];displacement=b['x']-a['x']
    if not 1.5<dt<=30 or not 2<abs(displacement)<=7.2:return None,{'reason':'lateral_duration_or_displacement'}
    if max(abs(a['v']),abs(b['v']))>2:return None,{'reason':'lateral_endpoint_speed'}
    t=np.asarray(times,float)
    if len(t)<3 or abs(t[0]-a['t'])>.02 or abs(t[-1]-b['t'])>.02:return None,{'reason':'lateral_endpoint_times'}
    u=(t-a['t'])/dt;m=a['v']*dt;n=b['v']*dt
    x=(2*u**3-3*u*u+1)*a['x']+(u**3-2*u*u+u)*m+(-2*u**3+3*u*u)*b['x']+(u**3-u*u)*n
    v=((6*u*u-6*u)*a['x']+(3*u*u-4*u+1)*m+(-6*u*u+6*u)*b['x']+(3*u*u-2*u)*n)/dt
    acc=((12*u-6)*a['x']+(6*u-4)*m+(-12*u+6)*b['x']+(6*u-2)*n)/dt**2
    if max(abs(x))>18 or max(abs(v))>2 or max(abs(acc))>1.5:return None,{'reason':'lateral_motion_bounds'}
    # A large unexplained swerve is not ordinary lane-change evidence.
    if min(x)<min(a['x'],b['x'])-.5 or max(x)>max(a['x'],b['x'])+.5:return None,{'reason':'lateral_overshoot'}
    return np.column_stack([t,x,v,acc]),{'reason':'supported_candidate','lateral_displacement_m':float(displacement),
                                      'identity_scope':'same_sensor_session_object_only','lane_change':'estimated_not_verified'}

def supports(before,after,points):
    p=np.asarray(points,float);lateral,evidence=lateral_curve(before,after,p[:,0])
    if lateral is None:return False,evidence
    ax=np.diff(p[:,2])/np.diff(p[:,0]);ay=(lateral[:-1,3]+lateral[1:,3])/2
    if np.any(np.hypot(ax,ay)>4+1e-5):return False,{'reason':'combined_acceleration'}
    return True,evidence
