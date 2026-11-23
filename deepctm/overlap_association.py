"""Experimental associations in overlapping projected coverage, not gap filling.

No clock shift or position correction is fitted. Observations remain unchanged.
Coincident trajectories and measured size are evidence, not verified identity.
"""
import numpy as np
from .object_shape import discrepancy
from .global_association import solve_edges

def evidence(a,b):
    if a['direction']!=b['direction']:return None
    p=np.asarray(a['points'],float);q=np.asarray(b['points'],float)
    if min(len(p),len(q))<5:return None
    if np.any(np.diff(p[:,0])<=0) or np.any(np.diff(q[:,0])<=0):return None
    lo=max(p[0,0],q[0,0]);hi=min(p[-1,0],q[-1,0])
    if hi-lo<1:return None
    space_lo=max(min(p[:,1]),min(q[:,1]));space_hi=min(max(p[:,1]),max(q[:,1]))
    if space_hi-space_lo<10:return None
    rows=[]
    for t,x,v in p:
        if not lo<=t<=hi or not space_lo<=x<=space_hi:continue
        j=int(np.searchsorted(q[:,0],t,side='right'))
        if not 0<j<len(q) or q[j,0]-q[j-1,0]>1.5:continue
        xx=float(np.interp(t,q[j-1:j+1,0],q[j-1:j+1,1]));vv=float(np.interp(t,q[j-1:j+1,0],q[j-1:j+1,2]))
        rows.append((t,x,abs(xx-x),abs(v-vv)))
    if len(rows)<3:return None
    rows=np.asarray(rows)
    if np.ptp(rows[:,0])<1 or np.ptp(rows[:,1])<10:return None
    position=float(np.median(rows[:,2]));tail=float(np.quantile(rows[:,2],.95));speed=float(np.median(rows[:,3]))
    if position>3 or tail>5 or speed>3:return None
    size=discrepancy(a.get('shape_end'),b.get('shape_start'))
    motion=position/3+.25*speed/3
    return {'motion_cost':motion,'shape_discrepancy':size,'cost':motion+(.5*size if size is not None else 0),
            'overlap_samples':len(rows),'support_s':float(np.ptp(rows[:,0])),'median_position_disagreement_m':position,
            'p95_position_disagreement_m':tail,'median_speed_disagreement_mps':speed,
            'overlap_time':[float(rows[0,0]),float(rows[-1,0])],'identity':'unverified_projected_coverage_overlap'}

def associate(left,right,threshold=1.5,margin=.5):
    records={};motion_edges={};edges={}
    for i,a in enumerate(left):
        for j,b in enumerate(right):
            r=evidence(a,b)
            if r is None:continue
            if r['motion_cost']<threshold:motion_edges[i,j]=r['motion_cost']
            if r['cost']<threshold:edges[i,j]=r['cost'];records[i,j]=r
    base={(m['left'],m['right']) for m in solve_edges(len(left),len(right),motion_edges,unmatched_cost=threshold/2,margin=margin)}
    selected=solve_edges(len(left),len(right),edges,unmatched_cost=threshold/2,margin=margin)
    return [dict(m,evidence=records[m['left'],m['right']]) for m in selected
            if records[m['left'],m['right']]['shape_discrepancy'] is not None or (m['left'],m['right']) in base]
