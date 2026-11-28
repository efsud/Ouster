"""Experimental global partial assignment. Never deployed without validation.

Every endpoint has an explicit unmatched alternative. Confidence is the increase
in optimum cost when an assigned edge is forbidden, not a claim of identity.
"""
import numpy as np
from scipy.optimize import linear_sum_assignment
from .spatial_bridges import pair_cost,curve
from .matching_physics import reachability

def associate(left,right,params,threshold=1.5,margin=.25,max_distance=350):
    n,m=len(left),len(right)
    if not n or not m:return []
    costs=np.full((n+m,n+m),1e6);paths={}
    # Each unused endpoint costs half the allowed pair score. Bottom-right
    # dummy pairs are free, allowing any number of genuine unmatched tracks.
    costs[:n,m:]=threshold/2;costs[n:,:m]=threshold/2;costs[n:,m:]=0
    for i,a in enumerate(left):
        for j,b in enumerate(right):
            c=pair_cost(a,b,max_distance=max_distance)
            if c is None or c>=threshold or reachability(a,b,params) is not None:continue
            p=curve(a,b)
            if p is None:continue
            costs[i,j]=c;paths[i,j]=p
    rows,cols=linear_sum_assignment(costs);best=float(costs[rows,cols].sum());accepted=[]
    for i,j in zip(rows,cols):
        if (i,j) not in paths:continue
        alternative=costs.copy();alternative[i,j]=1e6
        ar,ac=linear_sum_assignment(alternative);separation=float(alternative[ar,ac].sum())-best
        if separation<margin:continue
        accepted.append({'left':int(i),'right':int(j),'cost':float(costs[i,j]),'margin':separation,'points':paths[i,j],'identity':'unverified_global_assignment'})
    return accepted
