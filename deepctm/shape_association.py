"""Experimental shape-assisted partial association with unmatched alternatives."""
from .spatial_bridges import pair_cost,curve
from .matching_physics import reachability
from .object_shape import discrepancy
from .global_association import solve_edges

def associate(left,right,params,weight=.25,threshold=1.5,margin=.25,max_distance=350):
    edges={};paths={};shape_scores={};baseline_edges={}
    for i,a in enumerate(left):
        for j,b in enumerate(right):
            score=pair_cost(a,b,max_distance=max_distance)
            if score is None or score>=threshold or reachability(a,b,params) is not None:continue
            points=curve(a,b)
            if points is None:continue
            baseline_edges[i,j]=score
            shape=discrepancy(a.get('shape'),b.get('shape'))
            # Missing sizes remain baseline-cost competitors; they cannot gain
            # a new assignment solely because other edges receive size penalties.
            cost=score+(weight*shape if shape is not None else 0)
            if cost>=threshold:continue
            edges[i,j]=cost;paths[i,j]=points;shape_scores[i,j]=shape
    baseline={(m['left'],m['right']) for m in solve_edges(len(left),len(right),baseline_edges,unmatched_cost=threshold/2,margin=margin)}
    selected=solve_edges(len(left),len(right),edges,unmatched_cost=threshold/2,margin=margin)
    selected=[m for m in selected if shape_scores[m['left'],m['right']] is not None or (m['left'],m['right']) in baseline]
    for match in selected:
        key=(match['left'],match['right']);match['points']=paths[key];match['shape_discrepancy']=shape_scores[key]
    return selected
