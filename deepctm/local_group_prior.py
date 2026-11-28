"""Retrospective local-gap shapes learned from observed trajectory-group peers.

This is an optional shape prior, not an identity matcher or a heatmap. The caller
supplies visible target fragments and endpoints; hidden target samples are never
arguments. Every fragment of the target session/object is excluded from donors.
Only positions inside the missing interval are returned. A separate validation
report must authorize a replacement of the established kinematic estimate.
"""
import math
import time
from dataclasses import asdict

import numpy as np
from scipy.optimize import minimize_scalar

from .trajectory_reconstruction import baseline, refine

DEFAULTS = dict(max_gap_s=20., max_shift_s=20., max_offset_m=25.,
                max_visible_rmse_m=3., max_visible_speed_mae_mps=2.,
                max_consensus_spread_m=5., min_donors=3, max_donors=8,
                context_s=4., smoothness=.01, weight=.25)


def object_identity(track):
    """Classification changes do not create a new local object identity."""
    key = track.get('source_key', [])
    return tuple(str(v) for v in key[:2]) if len(key) >= 2 else None


def _runs(points):
    p = np.asarray(points, float)
    if p.ndim != 2 or p.shape[1] < 3 or len(p) < 5 or not np.all(np.isfinite(p[:, :3])):
        return []
    cuts = np.flatnonzero((np.diff(p[:, 0]) > 1.5) | (np.diff(p[:, 0]) <= 0)) + 1
    return [r for r in np.split(p[:, :3], cuts) if len(r) >= 5]


def _fit_donor(run, visible, grid, config):
    """Fit translation using visible x/speed only, then sample continuous donor."""
    lo = max(-config['max_shift_s'], run[0, 0] - visible[0, 0])
    hi = min(config['max_shift_s'], run[-1, 0] - visible[-1, 0])
    if hi < lo:
        return None

    def evaluate(shift):
        x = np.interp(visible[:, 0] + shift, run[:, 0], run[:, 1])
        offset = float(np.median(visible[:, 1] - x))
        err = x + offset - visible[:, 1]
        speed = np.interp(visible[:, 0] + shift, run[:, 0], run[:, 2])
        speed_err = speed - visible[:, 2]
        loss = float(np.mean(err**2) + 1.5 * np.mean(speed_err**2))
        if abs(offset) > config['max_offset_m']:
            loss += 10 * (abs(offset) - config['max_offset_m'])**2
        return loss, offset, float(np.sqrt(np.mean(err**2))), float(np.mean(abs(speed_err)))

    shifts = np.linspace(lo, hi, max(2, math.ceil((hi - lo) / .5) + 1))
    best = min(shifts, key=lambda shift: evaluate(shift)[0])
    lower, upper = max(lo, best - .5), min(hi, best + .5)
    if upper > lower:
        fit = minimize_scalar(lambda shift: evaluate(shift)[0], bounds=(lower, upper), method='bounded')
        best = float(fit.x)
    loss, offset, rmse, speed_mae = evaluate(best)
    if abs(offset) > config['max_offset_m'] or rmse > config['max_visible_rmse_m'] or speed_mae > config['max_visible_speed_mae_mps']:
        return None
    x = np.interp(grid + best, run[:, 0], run[:, 1]) + offset
    return dict(x=x, shift_s=float(best), offset_m=offset,
                visible_rmse_m=rmse, visible_speed_mae_mps=speed_mae, score=loss)


def prepare(site, target_visible, a, b, groups=None, config=None):
    """Create a reusable peer prior. Inputs a/b are ORIGINAL signed coordinates.

    Group discovery excludes every target identity fragment. The supplied target
    must have a hole: any target sample strictly inside a..b raises ValueError.
    Membership, time shift and position offset use visible data only. The donor
    curve may use observations inside this clock interval from OTHER objects.
    """
    config = {**DEFAULTS, **(config or {})}
    duration = b['t'] - a['t']
    if not 1.5 < duration <= config['max_gap_s']:
        return dict(state='unavailable', reason='gap_outside_validated_candidate_range')
    identity = object_identity(target_visible)
    if identity is None:
        return dict(state='unavailable', reason='target_identity_missing')
    p = np.asarray(target_visible.get('points', []), float)
    if p.ndim != 2 or p.shape[1] < 3:
        return dict(state='unavailable', reason='visible_context_missing')
    if np.any((p[:, 0] > a['t'] + 1e-7) & (p[:, 0] < b['t'] - 1e-7)):
        raise ValueError('Hidden target samples must not enter group reconstruction')
    sign = 1 if target_visible.get('direction') == 'eastbound' else -1
    aa, bb = dict(a, x=sign*a['x'], v=sign*a['v']), dict(b, x=sign*b['x'], v=sign*b['v'])
    if min(aa['v'], bb['v']) < 0 or bb['x'] < aa['x']:
        return dict(state='unavailable', reason='endpoint_direction_conflict')
    before = p[(p[:, 0] <= a['t']) & (p[:, 0] >= a['t'] - config['context_s'])]
    after = p[(p[:, 0] >= b['t']) & (p[:, 0] <= b['t'] + config['context_s'])]
    if len(before) < 4 or len(after) < 4:
        return dict(state='unavailable', reason='insufficient_visible_context')
    visible = np.vstack([before, after]).copy(); visible[:, 1] *= sign
    if groups is None:
        from .trajectory_groups import TrajectoryGroups
        groups = TrajectoryGroups(site)
    membership = groups.classify_visible(target_visible, excluded_identity=tuple(target_visible['source_key'][:2]))
    if not membership:
        return dict(state='unavailable', reason='no_supported_visible_group')
    t = baseline(aa, bb)[:, 0]
    fits = []
    for index in membership.get('donor_indices', []):
        donor = site['tracks'][index]
        donor_id = object_identity(donor)
        if donor_id is None or donor_id == identity or donor.get('method') or donor.get('direction') != target_visible.get('direction'):
            continue
        for run in _runs(donor.get('points', [])):
            run = run.copy(); run[:, 1] *= sign
            fit = _fit_donor(run, visible, t, config)
            if fit is not None:
                fits.append({**fit, 'index': int(index), 'identity': donor_id})
    # A fragmented peer ID is one independent donor, regardless of class labels.
    unique = {}
    for fit in sorted(fits, key=lambda f: (f['score'], f['index'])):
        unique.setdefault(fit['identity'], fit)
    fits = list(unique.values())[:config['max_donors']]
    if len(fits) < config['min_donors']:
        return dict(state='unavailable', reason='insufficient_continuous_group_donors', donor_count=len(fits), group_id=membership.get('group_id'))
    profiles = np.vstack([f['x'] for f in fits])
    x = np.median(profiles, axis=0)
    spread = float(np.max(np.median(abs(profiles - x), axis=0)))
    if spread > config['max_consensus_spread_m']:
        return dict(state='unavailable', reason='group_donor_disagreement', donor_count=len(fits), spread_m=spread)
    # Endpoint correction is fitted to observed endpoints, never hidden truth.
    u = (t - t[0]) / duration
    x += (1-u)*(aa['x']-x[0]) + u*(bb['x']-x[-1])
    v = np.gradient(x, t)
    reference = np.column_stack([t, x, v])
    return dict(state='prepared', reference=reference, a=aa, b=bb, sign=sign,
                group_id=membership.get('group_id'), donor_count=len(fits),
                donor_indices=[f['index'] for f in fits],
                donor_identities=[list(f['identity']) for f in fits],
                donor_fits=[{k: f[k] for k in ('index', 'shift_s', 'offset_m', 'visible_rmse_m', 'visible_speed_mae_mps')} for f in fits],
                consensus_spread_m=spread, config=config,
                evidence='observed peer group; target identity completely excluded')


def predict(prepared, parameters, weight=None):
    """Constrained peer-informed gap, ORIGINAL x sign and nonnegative speed.

    This function never changes an observed fragment. It does not authorize
    deployment: callers must check a separate frozen validation policy.
    """
    if prepared.get('state') != 'prepared':
        return prepared
    config = prepared['config']; weight = config['weight'] if weight is None else float(weight)
    if not 0 <= weight <= 1:
        raise ValueError('Peer-prior weight must lie in [0,1]')
    a, b = prepared['a'], prepared['b']
    base = baseline(a, b)
    reference = base.copy()
    reference[:, 1:] = (1-weight)*base[:, 1:] + weight*prepared['reference'][:, 1:]
    result = refine(a, b, reference, **parameters, smoothness=config['smoothness'],
                    position_tolerance=0., speed_tolerance=0.)
    if result['state'] != 'candidate':
        return dict(state=result['state'], reason=result.get('reason'), group_id=prepared['group_id'])
    points = result['points'].copy(); points[:, 1] *= prepared['sign']
    return dict(state='candidate', points=points, group_id=prepared['group_id'],
                donor_count=prepared['donor_count'], donor_indices=prepared['donor_indices'],
                donor_identities=prepared['donor_identities'], donor_fits=prepared['donor_fits'],
                consensus_spread_m=prepared['consensus_spread_m'], weight=weight,
                method='trajectory_group_peer_shape_v1', estimated=True,
                exact_endpoint_interpolation=True, max_gap_s=config['max_gap_s'],
                confidence='peer supported; uncertainty not probability calibrated')


def reconstruct(site, target_visible, a, b, parameters, groups=None, config=None):
    return predict(prepare(site, target_visible, a, b, groups=groups, config=config), parameters)


def apply(snapshot, baseline_layers, policy, parameters, group_indexes=None,
          max_attempts=50, max_seconds=5.):
    """Gated same-ID local replacement, always retaining baseline on abstention.

    ``baseline_layers`` is the reconstruction dictionary with ``within_intersection``.
    No new association is made and no between-site path is changed. The input is
    returned by value with a compact review record. A disabled/unknown policy
    performs no grouping. Work is capped for the rolling pipeline.
    """
    result = dict(baseline_layers)
    local = list(baseline_layers.get('within_intersection', [])); result['within_intersection'] = local
    audit = dict(state='disabled', attempted=0, replaced=0, baseline_retained=len(local))
    result['group_prior_review'] = audit
    if (not policy or not policy.get('enabled') or
        policy.get('version') != 'trajectory_group_peer_shape_v1' or
        policy.get('configuration') != DEFAULTS or
        policy.get('parameters') != parameters or
        policy.get('validation_state') != 'complete'):
        return result
    allowed = set(policy.get('enabled_sites', []))
    if not allowed:
        return result
    from .spatial_bridges import endpoint
    from .trajectory_groups import GroupConfig, TrajectoryGroups
    if policy.get('group_configuration') != asdict(GroupConfig()):
        return result
    groups = {} if group_indexes is None else group_indexes
    sites = {s['id']: s for s in snapshot['sites']}
    targets = {}
    for site_id in allowed & sites.keys():
        by_id = {}
        for tr in sites[site_id]['tracks']:
            if tr.get('method'):
                continue
            key = object_identity(tr)
            if key is not None:
                by_id.setdefault(key, []).append(tr)
        targets[site_id] = by_id
    started = time.monotonic(); audit['state'] = 'evaluated'
    for index, old in enumerate(local):
        if audit['attempted'] >= max_attempts or time.monotonic()-started >= max_seconds:
            audit['budget_exhausted'] = True
            break
        site_id = old.get('site'); key = old.get('identity_key', [])
        if site_id not in targets or len(key) < 2 or not str(old.get('identity', '')).startswith('same_sensor'):
            continue
        old_points = old.get('points', [])
        if len(old_points) < 2:
            continue
        start, end = old_points[0][0], old_points[-1][0]
        if not 1.5 < end-start <= DEFAULTS['max_gap_s']:
            continue
        fragments = targets[site_id].get(tuple(str(v) for v in key[:2]), [])
        if not fragments:
            continue
        points = sorted({tuple(p[:3]) for tr in fragments for p in tr['points']})
        if any(start+1e-6 < p[0] < end-1e-6 for p in points):
            continue
        before = [p for p in points if p[0] <= start+1e-6]
        after = [p for p in points if p[0] >= end-1e-6]
        a, b = endpoint(before, True), endpoint(after, False)
        if a is None or b is None or abs(a['t']-start) > .02 or abs(b['t']-end) > .02:
            continue
        if abs(a['x']-old_points[0][1]) > .05 or abs(b['x']-old_points[-1][1]) > .05:
            continue
        left = min(fragments, key=lambda tr: abs(tr['points'][-1][0]-start))
        right = min(fragments, key=lambda tr: abs(tr['points'][0][0]-end))
        target = dict(source_key=list(key[:2])+[old.get('class_type', '2')],
                      class_type=old.get('class_type', '2'), direction=old.get('direction'),
                      points=before+after, movement={'state': 'unknown'},
                      lateral_start_m=left.get('lateral_start_m'), lateral_end_m=right.get('lateral_end_m'))
        audit['attempted'] += 1
        if site_id not in groups:
            groups[site_id] = TrajectoryGroups(sites[site_id])
        proposal = reconstruct(sites[site_id], target, a, b, parameters,
                               groups[site_id], dict(weight=policy['weight']))
        if proposal['state'] != 'candidate':
            continue
        local[index] = {**old, **{k: v for k, v in proposal.items() if k not in ('state', 'points')},
                        'points': proposal['points'].tolist(),
                        'baseline_provenance': {k: old.get(k) for k in ('method', 'estimation_model', 'identity', 'gap_kind')},
                        'group_validation_report': policy.get('evidence')}
        audit['replaced'] += 1
    audit.update(baseline_retained=len(local)-audit['replaced'], elapsed_s=round(time.monotonic()-started, 3))
    return result
