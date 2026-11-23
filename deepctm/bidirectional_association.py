"""Experimental two-sided motion evidence; no identity labels enter costs."""
import math
import numpy as np
from collections import Counter
from .spatial_bridges import pair_cost
from .matching_physics import reachability
from .kinematic_gate import path
from .object_shape import discrepancy
from .global_association import solve_edges

def motion_context(points,exit_side):
    p=np.asarray(points,float)
    if len(p)<6:return None
    anchor=p[-1,0] if exit_side else p[0,0]
    p=p[abs(p[:,0]-anchor)<=3]
    if len(p)<6 or p[-1,0]-p[0,0]<2 or np.any(np.diff(p[:,0])<=0) or np.any(np.diff(p[:,0])>1.5):return None
    t=p[:,0]-anchor
    co=np.polyfit(t,p[:,1],2);residual=float(np.sqrt(np.mean((np.polyval(co,t)-p[:,1])**2)))
    acceleration=float(2*co[0])
    if residual>1 or abs(acceleration)>3:return None
    return dict(acceleration_mps2=acceleration,fit_rmse_m=residual,duration_s=float(np.ptp(t)))

def extrapolate(ep,seconds,params):
    """Signed time integration, acceleration trusted for at most three seconds."""
    context=ep.get('motion_context')
    accel=context['acceleration_mps2'] if context else 0.
    sign=1 if ep['v']>=0 else -1
    # Numerical integration with stop/speed bounds, used only as a matching cue.
    n=max(1,math.ceil(abs(seconds)/.25));h=seconds/n;x=ep['x'];v=ep['v']
    for k in range(n):
        dv=accel*h if abs((k+.5)*h)<=3 else 0
        new=sign*min(params['vmax'],max(0,sign*(v+dv)))
        x+=(v+new)*h/2;v=new
    return x,v

def two_sided_cost(a,b,params):
    dt=b['t']-a['t'];dx=abs(b['x']-a['x'])
    if dt<=0:return None
    if not a.get('motion_context') or not b.get('motion_context'):return None
    xa,va=extrapolate(a,dt/2,params);xb,vb=extrapolate(b,-dt/2,params)
    # Dimensionless residual; fixed constants, not confidence probabilities.
    return abs(xa-xb)/max(5,.35*dx)+abs(va-vb)/15

def associate(left,right,params,blend=0.,threshold=1.5,margin=.25,max_distance=350,diagnostics=None):
    counts=Counter();edges={};base_edges={};paths={};shapes={}
    for i,a in enumerate(left):
        for j,b in enumerate(right):
            counts['all_pairs']+=1
            dt=b['t']-a['t'];dx=b['x']-a['x'];sign=1 if dx>0 else -1
            if not 0<dt<=120:counts['outside_time_window']+=1;continue
            counts['time_eligible_pairs']+=1
            if not 2<abs(dx)<max_distance:counts['distance_or_overlap']+=1;continue
            if min(a['v']*sign,b['v']*sign)<1:counts['direction_or_low_endpoint_speed']+=1;continue
            score=pair_cost(a,b,max_distance)
            if score is None:counts['average_speed_bound']+=1;continue
            motion=two_sided_cost(a,b,params) if blend else None
            if motion is not None:score=(1-blend)*score+blend*motion
            if score>=threshold:counts['motion_score']+=1;continue
            reason=reachability(a,b,params)
            if reason:counts['physics_'+reason]+=1;continue
            points=path(a,b,params)
            if points is None:counts['exact_velocity_gate']+=1;continue
            base_edges[i,j]=score
            shape=discrepancy(a.get('shape'),b.get('shape'))
            cost=score+(.5*shape if shape is not None else 0)
            if cost>=threshold:counts['shape_score']+=1;continue
            edges[i,j]=cost;paths[i,j]=points;shapes[i,j]=shape
    baseline={(m['left'],m['right']) for m in solve_edges(len(left),len(right),base_edges,unmatched_cost=threshold/2,margin=margin)}
    selected=solve_edges(len(left),len(right),edges,unmatched_cost=threshold/2,margin=margin)
    result=[]
    for m in selected:
        key=m['left'],m['right']
        if shapes[key] is None and key not in baseline:counts['missing_shape_competitor']+=1;continue
        result.append(dict(m,points=paths[key]))
    counts['feasible_edges']=len(edges);counts['assigned_pairs']=len(result)
    counts['unmatched_departures']=len(left)-len(result);counts['unmatched_arrivals']=len(right)-len(result)
    counts['departures_without_feasible_edge']=len(left)-len({i for i,j in edges})
    counts['departures_with_edges_but_unassigned']=len({i for i,j in edges})-len(result)
    if diagnostics is not None:diagnostics.update(counts)
    return result
