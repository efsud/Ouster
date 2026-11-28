"""Candidate endpoint-time slope evidence for the existing partial matcher.

The production endpoint speed is a median over observed segments. During
acceleration it need not equal the derivative at the endpoint time. This module
tests a bounded correction to the bidirectional *scoring cue* only. Original
endpoint positions/speeds still determine every physical and path gate.
"""
from collections import Counter
import math

import numpy as np

from .bidirectional_association import associate as baseline_associate, motion_context, two_sided_cost
from .global_association import solve_edges
from .kinematic_gate import path
from .matching_physics import reachability
from .object_shape import discrepancy
from .spatial_bridges import pair_cost

VERSION = 'bounded_endpoint_time_slope_v2'
BASELINE = dict(blend=.5, threshold=1.5, margin=.25, max_distance=350)
CANDIDATES = (1., 2.)


def enrich(endpoint, points, exit_side):
    """Observed-side context; never accepts samples on the hidden side."""
    ep = dict(endpoint)
    p = np.asarray(points, float)
    ep['motion_context'] = None
    if p.ndim != 2 or p.shape[1] < 2 or not np.isfinite(p).all():
        return ep
    anchor = ep['t']
    if (exit_side and np.any(p[:, 0] > anchor+1e-6)) or (not exit_side and np.any(p[:, 0] < anchor-1e-6)):
        raise ValueError('Endpoint context includes samples from the hidden side')
    ep['motion_context'] = motion_context(p, exit_side)
    if ep['motion_context'] is None:
        return ep
    q = p[abs(p[:, 0]-anchor) <= 3.]
    t = q[:, 0]-anchor
    coef = np.polyfit(t, q[:, 1], 2)
    instantaneous = float(coef[1])
    # Drop the furthest observed sample. A fixed two-second window often holds
    # only four samples at the real ~0.55s cadence, silently disabling the cue.
    # This shorter fit still needs five actual samples and >=1.5s duration.
    short = q[1:] if exit_side else q[:-1]
    if len(short) < 5 or np.ptp(short[:, 0]) < 1.5:
        return ep
    short_coef = np.polyfit(short[:, 0]-anchor, short[:, 1], 2)
    short_error = float(np.sqrt(np.mean((np.polyval(short_coef, short[:, 0]-anchor)-short[:, 1])**2)))
    sign = 1 if ep['v'] >= 0 else -1
    if (not math.isfinite(instantaneous) or sign*instantaneous < 1 or
            abs(instantaneous-float(short_coef[1])) > 1. or short_error > .5 or
            ep['motion_context']['fit_rmse_m'] > .5):
        return ep
    ep['endpoint_time_slope'] = dict(speed_mps=instantaneous,
        short_window_difference_mps=abs(instantaneous-float(short_coef[1])),
        fit_rmse_m=ep['motion_context']['fit_rmse_m'],
        observed_side='before' if exit_side else 'after',
        original_speed_mps=float(ep['v']))
    return ep


def corrected_cue(endpoint, cap_mps):
    """Return a private scoring copy; observed endpoints are never modified."""
    evidence = endpoint.get('endpoint_time_slope')
    if not evidence or not endpoint.get('motion_context'):
        return endpoint
    delta = float(evidence['speed_mps'])-endpoint['v']
    if not math.isfinite(delta):
        return endpoint
    return dict(endpoint, v=endpoint['v']+float(np.clip(delta, -cap_mps, cap_mps)))


def contextual_cost(a, b, parameters, cap_mps):
    aa, bb = corrected_cue(a, cap_mps), corrected_cue(b, cap_mps)
    return two_sided_cost(aa, bb, parameters)


def associate(left, right, parameters, cap_mps=None, diagnostics=None,
              blend=.5, threshold=1.5, margin=.25, max_distance=350):
    """Exact old matcher when cap is None; candidate changes one scoring cue."""
    if cap_mps is None:
        return baseline_associate(left, right, parameters, blend=blend,
            threshold=threshold, margin=margin, max_distance=max_distance, diagnostics=diagnostics)
    if cap_mps not in CANDIDATES:
        raise ValueError('Use a predeclared endpoint correction cap')
    counts = Counter(); edges = {}; base_edges = {}; paths = {}; shapes = {}
    for i, a in enumerate(left):
        for j, b in enumerate(right):
            counts['all_pairs'] += 1
            dt = b['t']-a['t']; dx = b['x']-a['x']; sign = 1 if dx > 0 else -1
            if not 0 < dt <= 120:
                counts['outside_time_window'] += 1; continue
            counts['time_eligible_pairs'] += 1
            if not 2 < abs(dx) < max_distance:
                counts['distance_or_overlap'] += 1; continue
            if min(a['v']*sign, b['v']*sign) < 1:
                counts['direction_or_low_endpoint_speed'] += 1; continue
            score = pair_cost(a, b, max_distance)
            if score is None:
                counts['average_speed_bound'] += 1; continue
            motion = contextual_cost(a, b, parameters, cap_mps) if blend else None
            if motion is not None:
                score = (1-blend)*score+blend*motion
                if a.get('endpoint_time_slope') or b.get('endpoint_time_slope'):
                    counts['corrected_context_pairs'] += 1
            if score >= threshold:
                counts['motion_score'] += 1; continue
            reason = reachability(a, b, parameters)
            if reason:
                counts['physics_'+reason] += 1; continue
            points = path(a, b, parameters)
            if points is None:
                counts['exact_velocity_gate'] += 1; continue
            base_edges[i, j] = score
            shape = discrepancy(a.get('shape'), b.get('shape'))
            cost = score+(.5*shape if shape is not None else 0)
            if cost >= threshold:
                counts['shape_score'] += 1; continue
            edges[i, j] = cost; paths[i, j] = points; shapes[i, j] = shape
    no_shape = {(m['left'], m['right']) for m in solve_edges(
        len(left), len(right), base_edges, unmatched_cost=threshold/2, margin=margin)}
    selected = solve_edges(len(left), len(right), edges, unmatched_cost=threshold/2, margin=margin)
    result = []
    for m in selected:
        key = m['left'], m['right']
        if shapes[key] is None and key not in no_shape:
            counts['missing_shape_competitor'] += 1; continue
        result.append(dict(m, points=paths[key], method=VERSION,
            cap_mps=cap_mps, cross_sensor_identity_verified=False))
    counts.update(feasible_edges=len(edges), assigned_pairs=len(result),
        unmatched_departures=len(left)-len(result), unmatched_arrivals=len(right)-len(result),
        departures_without_feasible_edge=len(left)-len({i for i, j in edges}),
        departures_with_edges_but_unassigned=len({i for i, j in edges})-len(result))
    if diagnostics is not None:
        diagnostics.update(counts)
    return result
