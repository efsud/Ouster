"""Self-supervised local-regime peer shapes for individual missing trajectories.

The unsupervised stage supplies independent observed peers with matching local
time, path, slope and speed. A ridge model learns how much their observed shape
should influence a missing individual segment. Training labels are obtained by
hiding recorded positions. No hidden positions are inputs at prediction time.

This is retrospective local reconstruction, not a cross-sensor identity matcher.
The optional production adapter requires a separately qualified frozen policy.
"""
import hashlib
import json
import time

import numpy as np

from .local_group_prior import DEFAULTS, object_identity, prepare as peer_prepare, predict as peer_predict
from .trajectory_reconstruction import baseline

VERSION = 'local_regime_learned_peer_v1'
FEATURES = ('duration_s', 'required_speed_mps', 'start_speed_mps', 'end_speed_mps',
            'speed_change_mps', 'endpoint_acceleration_mps2', 'donor_count',
            'donor_visible_rmse_m', 'donor_visible_speed_mae_mps', 'donor_spread_m',
            'peer_base_rms_m', 'peer_base_rms_speed_mps', 'stopped_endpoints',
            'one_stopped_endpoint')


class BoundRegimeGroups:
    """Adapt the common peer fitter without widening its identity checks."""
    def __init__(self, groups, a, b):
        self.groups, self.a, self.b = groups, a, b

    def classify_visible(self, target, excluded_identity):
        return self.groups.select_donors(target, self.a, self.b,
                                         excluded_identity=excluded_identity)


def prepare(site, target_visible, a, b, groups=None, config=None):
    if groups is None:
        from .trajectory_regime_groups import TrajectoryRegimeGroups
        groups = TrajectoryRegimeGroups(site)
    result = peer_prepare(site, target_visible, a, b,
                          BoundRegimeGroups(groups, a, b), config)
    if result.get('state') == 'prepared':
        result['grouping'] = 'local_time_path_speed_slope_regimes'
    return result


def features(prepared):
    """Features are only endpoint observations and independent peer evidence."""
    if prepared.get('state') != 'prepared':
        raise ValueError('Features require a prepared observed-peer prior')
    a, b = prepared['a'], prepared['b']
    duration = b['t'] - a['t']
    ref = np.asarray(prepared['reference'], float)
    base = baseline(a, b)
    fits = prepared['donor_fits']
    values = [duration, (b['x']-a['x'])/duration, a['v'], b['v'],
              b['v']-a['v'], (b['v']-a['v'])/duration,
              prepared['donor_count'],
              np.mean([f['visible_rmse_m'] for f in fits]),
              np.mean([f['visible_speed_mae_mps'] for f in fits]),
              prepared['consensus_spread_m'],
              np.sqrt(np.mean((ref[:, 1]-base[:, 1])**2)),
              np.sqrt(np.mean((ref[:, 2]-base[:, 2])**2)),
              float(max(a['v'], b['v']) < .5),
              float(min(a['v'], b['v']) < .5 <= max(a['v'], b['v']))]
    result = np.asarray(values, float)
    if len(result) != len(FEATURES) or not np.all(np.isfinite(result)):
        raise ValueError('Nonfinite or malformed visible group features')
    return result


def training_label(prepared, hidden_truth):
    """Training-only optimal bounded weight for peer minus kinematic residual.

    Hidden truth uses oriented increasing position, as in masking benchmarks.
    This function is never called by the prediction or deployment interfaces.
    Position and speed residuals are jointly fit; alpha is clipped to [0,1].
    """
    truth = np.asarray(hidden_truth, float)
    base = baseline(prepared['a'], prepared['b'])
    peer = prepared['reference']
    t = truth[:, 0]
    bx, bv = (np.interp(t, base[:, 0], base[:, c]) for c in (1, 2))
    px, pv = (np.interp(t, peer[:, 0], peer[:, c]) for c in (1, 2))
    # One second converts velocity to a position-scale residual. This weight
    # is predeclared, not chosen by the held-out trajectories.
    delta = np.r_[px-bx, pv-bv]
    error = np.r_[truth[:, 1]-bx, truth[:, 2]-bv]
    if not np.all(np.isfinite(np.r_[delta, error])):
        raise ValueError('Training samples must be finite')
    denominator = float(delta @ delta)
    return float(np.clip(delta @ error / denominator, 0., 1.)) if denominator > 1e-8 else 0.


def fit(rows, ridge=10., min_ids=20):
    """Fit on training masks only, weighting repeated masks per ID equally."""
    rows = [r for r in rows if 'features' in r and 'target_weight' in r]
    ids = {r['identity_hash'] for r in rows}
    if len(ids) < min_ids:
        return dict(state='insufficient_training', version=VERSION,
                    independent_ids=len(ids), samples=len(rows), minimum_ids=min_ids)
    x = np.asarray([r['features'] for r in rows], float)
    y = np.asarray([r['target_weight'] for r in rows], float)
    if x.shape != (len(rows), len(FEATURES)) or not np.all(np.isfinite(x)) or not np.all(np.isfinite(y)):
        raise ValueError('Training features and labels must be finite')
    if not np.all((0 <= y) & (y <= 1)) or ridge <= 0:
        raise ValueError('Labels must be bounded and regularization positive')
    counts = {i: sum(r['identity_hash'] == i for r in rows) for i in ids}
    weights = np.asarray([1/counts[r['identity_hash']] for r in rows])
    weights *= len(rows)/weights.sum()
    mean = np.average(x, axis=0, weights=weights)
    scale = np.sqrt(np.average((x-mean)**2, axis=0, weights=weights))
    scale = np.maximum(scale, 1e-6)
    design = np.c_[np.ones(len(x)), (x-mean)/scale]
    penalty = np.eye(len(FEATURES)+1)*ridge; penalty[0, 0] = 0
    beta = np.linalg.solve(design.T @ (weights[:, None]*design)+penalty,
                           design.T @ (weights*y))
    model = dict(state='trained', version=VERSION, feature_names=list(FEATURES),
                 mean=mean.tolist(), scale=scale.tolist(), coefficients=beta.tolist(),
                 ridge=float(ridge), training_ids=sorted(ids), independent_ids=len(ids),
                 samples=len(rows), minimum_ids=min_ids,
                 label_definition='bounded_joint_position_speed_peer_residual',
                 training_label_mean=float(np.average(y, weights=weights)))
    model['fingerprint'] = fingerprint(model)
    return model


def fingerprint(model):
    return hashlib.sha256(json.dumps({k: v for k, v in model.items() if k != 'fingerprint'},
                                    sort_keys=True, allow_nan=False).encode()).hexdigest()


def weight(model, values):
    if model.get('state') != 'trained' or model.get('version') != VERSION:
        raise ValueError('A trained local-regime model is required')
    if model.get('feature_names') != list(FEATURES) or model.get('fingerprint') != fingerprint(model):
        raise ValueError('Model feature schema or fingerprint mismatch')
    x = np.asarray(values, float); mean = np.asarray(model['mean'], float)
    scale = np.asarray(model['scale'], float); beta = np.asarray(model['coefficients'], float)
    if (x.shape != (len(FEATURES),) or mean.shape != x.shape or scale.shape != x.shape or
        beta.shape != (len(FEATURES)+1,) or np.any(scale <= 0) or
        not np.all(np.isfinite(np.r_[x, mean, scale, beta]))):
        raise ValueError('Malformed or nonfinite prediction features/model')
    return float(np.clip(beta[0] + ((x-mean)/scale) @ beta[1:], 0., 1.))


def predict(prepared, parameters, model):
    if prepared.get('state') != 'prepared':
        return prepared
    if model.get('state') != 'trained':
        return dict(state='unavailable', reason='insufficient_training')
    alpha = weight(model, features(prepared))
    result = peer_predict(prepared, parameters, alpha)
    if result.get('state') == 'candidate':
        result.update(method=VERSION, learned_weight=alpha,
                      model_fingerprint=model['fingerprint'],
                      learning='self_supervised_recorded_masked_group_peers')
    return result


def propose(site, target_visible, a, b, parameters, policy, groups=None,
            started=None, max_seconds=2.):
    """Bounded optional adapter; never changes observations or invents identity.

    It returns one proposal only when a frozen per-site review enabled the model.
    The caller retains its baseline on every noncandidate result. Runtime budget
    is checked before and after preparation; a single grouping call may finish
    before this soft budget is observed. No pipeline installs this automatically.
    """
    started = time.monotonic() if started is None else started
    if (not policy or not policy.get('enabled') or policy.get('version') != VERSION or
        policy.get('validation_state') != 'complete' or site.get('id') not in policy.get('enabled_sites', []) or
        policy.get('parameters') != parameters or policy.get('configuration') != DEFAULTS):
        return dict(state='unavailable', reason='policy_not_qualified')
    from dataclasses import asdict
    from .trajectory_regime_groups import RegimeGroupConfig
    if policy.get('group_configuration') != asdict(RegimeGroupConfig()):
        return dict(state='unavailable', reason='group_configuration_changed')
    if time.monotonic()-started >= max_seconds:
        return dict(state='unavailable', reason='runtime_budget')
    prepared = prepare(site, target_visible, a, b, groups)
    if time.monotonic()-started >= max_seconds:
        return dict(state='unavailable', reason='runtime_budget')
    return predict(prepared, parameters, policy.get('model', {}))


def apply(snapshot, baseline_layers, policy, parameters, group_indexes=None,
          max_attempts=40, max_seconds=5.):
    """Optional bounded replacements of existing supported class-2 same-ID gaps.

    Every noncandidate keeps the previous estimate. Original observations,
    between-site associations and unvalidated object classes are untouched.
    The soft budget is checked around expensive calls; it cannot interrupt one
    already running solver. Group indexes may be shared with the viewer worker.
    """
    from dataclasses import asdict
    from .spatial_bridges import endpoint
    from .trajectory_regime_groups import RegimeGroupConfig, TrajectoryRegimeGroups

    result = dict(baseline_layers)
    local = list(baseline_layers.get('within_intersection', []))
    result['within_intersection'] = local
    audit = dict(state='disabled', attempted=0, replaced=0, baseline_retained=len(local),
                 scope='class2_same_sensor_session_object_id_local_gaps_up_to20s', reasons={})
    result['regime_learning_review'] = audit
    if (not policy or not policy.get('enabled') or policy.get('version') != VERSION or
        policy.get('validation_state') != 'complete' or policy.get('parameters') != parameters or
        policy.get('configuration') != DEFAULTS or
        policy.get('group_configuration') != asdict(RegimeGroupConfig()) or
        not policy.get('evidence') or not policy.get('snapshot_sha256')):
        audit['reason'] = 'policy_not_qualified_or_configuration_changed'
        return result
    model = policy.get('model', {})
    try:
        weight(model, np.zeros(len(FEATURES)))
    except (ValueError, KeyError, TypeError, OverflowError):
        audit['reason'] = 'model_schema_fingerprint_or_values_invalid'
        return result
    allowed = set(policy.get('enabled_sites', []))
    sites = {s['id']: s for s in snapshot['sites'] if s['id'] in allowed}
    if not sites:
        audit['reason'] = 'no_qualified_sites'
        return result
    groups = {} if group_indexes is None else group_indexes
    targets = {}
    for site_id, site in sites.items():
        by_identity = {}
        for tr in site['tracks']:
            key = object_identity(tr)
            if key is not None and not tr.get('method'):
                by_identity.setdefault(key, []).append(tr)
        targets[site_id] = by_identity
    started = time.monotonic(); audit['state'] = 'evaluated'
    for index, old in enumerate(local):
        if audit['attempted'] >= max_attempts or time.monotonic()-started >= max_seconds:
            audit['budget_exhausted'] = True
            break
        site_id = old.get('site'); key = old.get('identity_key', [])
        if (site_id not in sites or len(key) < 2 or str(old.get('class_type')) != '2' or
            not str(old.get('identity', '')).startswith('same_sensor')):
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
        before, after = [p for p in points if p[0] <= start+1e-6], [p for p in points if p[0] >= end-1e-6]
        a, b = endpoint(before, True), endpoint(after, False)
        if a is None or b is None or abs(a['t']-start) > .02 or abs(b['t']-end) > .02:
            continue
        if abs(a['x']-old_points[0][1]) > .05 or abs(b['x']-old_points[-1][1]) > .05:
            continue
        left = min(fragments, key=lambda tr: abs(tr['points'][-1][0]-start))
        right = min(fragments, key=lambda tr: abs(tr['points'][0][0]-end))
        target = dict(source_key=list(key[:2])+['2'], class_type='2',
            direction=old.get('direction'), points=before+after, movement={'state': 'unknown'},
            lateral_start_m=left.get('lateral_start_m'), lateral_end_m=right.get('lateral_end_m'))
        audit['attempted'] += 1
        if site_id not in groups:
            groups[site_id] = TrajectoryRegimeGroups(sites[site_id])
        proposal = propose(sites[site_id], target, a, b, parameters, policy,
                           groups[site_id], started, max_seconds)
        if proposal['state'] != 'candidate':
            reason = proposal.get('reason', proposal['state'])
            audit['reasons'][reason] = audit['reasons'].get(reason, 0)+1
            continue
        local[index] = {**old, **{k: v for k, v in proposal.items() if k not in ('state', 'points')},
            'points': proposal['points'].tolist(),
            'baseline_provenance': {k: old.get(k) for k in ('method', 'estimation_model', 'identity', 'gap_kind')},
            'regime_validation_report': policy['evidence']}
        audit['replaced'] += 1
    audit.update(baseline_retained=len(local)-audit['replaced'], elapsed_s=round(time.monotonic()-started, 3))
    return result
