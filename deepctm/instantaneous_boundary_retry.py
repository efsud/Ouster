"""Local same-ID retry using instantaneous speeds from visible acceleration.

The established median step speed describes the middle of a visible flank, not
necessarily its boundary. A one-sided, endpoint-anchored quadratic position fit
can estimate the boundary speed when a vehicle begins to accelerate immediately
after a missing interval. Only missing points are generated; observed positions,
timestamps, IDs and clock/lateral admission checks remain unchanged.
"""
import numpy as np
from scipy.optimize import minimize

from .endpoint_context import select
from .endpoint_speed import orient
from .reconstruction_layers import prediction
from .trajectory_reconstruction import baseline, refine
from .adaptive_endpoint_grid import retry as adaptive_retry

VERSION = 'visible_instantaneous_boundary_retry_v1'
DEFAULTS = dict(max_speed_adjustment_mps=2., max_fit_rmse_m=.15,
                max_fit_error_m=.45, minimum_acceleration_mps2=.5,
                min_context_s=1., max_context_s=4., max_gap_s=60.)
NOISE_POLICY = dict(negative_speed_limit_mps=.1, position_span_limit_m=.1,
                    trend_limit_mps=.05, step_speed_limit_mps=.5)
NOISE_EXCLUDED_SITES = {'OBC-AG-SA-C257223'}
_NOT_COMPUTED = object()


def established_prediction(site_id, a, b, report, classes=('2', '2'), stationary_admission=False):
    """The deployed local physical baseline, including existing fallbacks."""
    from .stationary_plateau import estimate
    car = all(str(v) == '2' for v in classes)
    correction = car and site_id not in NOISE_EXCLUDED_SITES
    if stationary_admission:
        result = estimate(a, b, same_identity=True)
        return result.get('points') if result['state'] == 'candidate' else None
    return prediction(a, b, report, exact_join=True,
        endpoint_policy=NOISE_POLICY if correction and 1.5 < b['t']-a['t'] <= 90 else None,
        stationary_plateau=correction, adaptive_grid=car)


def boundary_fit(points, exit_side, sign, parameters, config=None):
    """Fit x(t)=x_boundary+v*t+0.5*a*t² to one observed flank only."""
    cfg = DEFAULTS | (config or {})
    p = np.asarray(select(points, exit_side), float)
    if p.ndim != 2 or p.shape[1] < 3 or len(p) < 5 or not np.all(np.isfinite(p[:, :3])):
        return dict(state='unavailable', reason='invalid_visible_flank')
    dt = np.diff(p[:, 0]); duration = p[-1, 0]-p[0, 0]
    if np.any(dt <= 0) or np.any(dt > 1.5) or not cfg['min_context_s'] <= duration <= cfg['max_context_s']:
        return dict(state='unavailable', reason='noncontinuous_visible_flank')
    anchor = -1 if exit_side else 0
    t = p[:, 0]-p[anchor, 0]
    x = sign*(p[:, 1]-p[anchor, 1])
    design = np.column_stack([t, .5*t*t])
    vmax, amin, amax = (parameters[k] for k in ('vmax', 'amin', 'amax'))
    raw = np.linalg.lstsq(design, x, rcond=None)[0]
    initial = np.clip(raw, [0., amin], [vmax, amax])
    speed_design = np.column_stack([np.ones(len(t)), t])
    def objective(beta):
        error = design@beta-x
        return float(error@error), 2*design.T@error
    result = minimize(objective, initial, method='SLSQP', jac=True,
        bounds=[(0., vmax), (amin, amax)],
        constraints=[dict(type='ineq', fun=lambda q: speed_design@q,
                          jac=lambda q: speed_design),
                     dict(type='ineq', fun=lambda q: vmax-speed_design@q,
                          jac=lambda q: -speed_design)],
        options=dict(maxiter=60, ftol=1e-10))
    if not result.success or not np.all(np.isfinite(result.x)):
        return dict(state='unavailable', reason='visible_fit_failed')
    v, acc = map(float, result.x); errors = design@result.x-x
    rmse, maximum = float(np.sqrt(np.mean(errors**2))), float(np.max(abs(errors)))
    if rmse > cfg['max_fit_rmse_m'] or maximum > cfg['max_fit_error_m']:
        return dict(state='unavailable', reason='visible_fit_residual', fit_rmse_m=rmse, fit_max_error_m=maximum)
    return dict(state='fitted', speed_mps=v, acceleration_mps2=acc,
                fit_rmse_m=rmse, fit_max_error_m=maximum,
                visible_duration_s=float(duration), visible_samples=len(p),
                raw_boundary_speed_mps=float(raw[0]),
                context_start_s=float(p[0, 0]), context_end_s=float(p[-1, 0]))


def reconstruct(site_id, before, after, a, b, direction, report, config=None,
                classes=('2', '2'), established=_NOT_COMPUTED):
    """Only retry rejected, already admitted same-ID local gaps.

    Admission is the caller's responsibility and must use the existing session,
    SDK/receipt clock, movement, lateral and long-outage evidence gates. This
    function cannot authorize a new match. Prediction has no hidden-data input.
    """
    cfg = DEFAULTS | (config or {})
    if any(str(c) != '2' for c in classes):
        return dict(state='unavailable', reason='outside_validated_class_scope')
    if not 1.5 < b['t']-a['t'] <= cfg['max_gap_s']:
        return dict(state='unavailable', reason='gap_duration')
    if any(a['t']+1e-7 < p[0] < b['t']-1e-7 for p in [*before, *after]):
        raise ValueError('Hidden points cannot enter the visible-boundary retry')
    if (not before or not after or any(p[0] > a['t']+1e-7 for p in before) or
        any(p[0] < b['t']-1e-7 for p in after) or
        abs(before[-1][0]-a['t']) > 1e-7 or abs(after[0][0]-b['t']) > 1e-7 or
        abs(before[-1][1]-a['x']) > 1e-7 or abs(after[0][1]-b['x']) > 1e-7):
        raise ValueError('Visible flanks must coincide with their supplied gap endpoints')
    old = established_prediction(site_id, a, b, report, classes) if established is _NOT_COMPUTED else established
    if old is not None:
        return dict(state='baseline_retained', points=np.asarray(old, float))
    sign = 1 if direction == 'eastbound' else -1
    aa, bb = orient(a, sign), orient(b, sign)
    if bb['x'] < aa['x'] or min(aa['v'], bb['v']) < -.25:
        return dict(state='unavailable', reason='reverse_endpoint_evidence')
    if site_id in NOISE_EXCLUDED_SITES and min(aa['v'], bb['v']) < 0:
        return dict(state='unavailable', reason='existing_stationary_noise_site_exclusion')
    params = report['calibration']['parameters']
    fits = [boundary_fit(before, True, sign, params, cfg), boundary_fit(after, False, sign, params, cfg)]
    if any(f['state'] != 'fitted' for f in fits):
        return dict(state='unavailable', reason='unsupported_visible_boundary_fit', fits=fits)
    if max(abs(f['acceleration_mps2']) for f in fits) < cfg['minimum_acceleration_mps2']:
        return dict(state='unavailable', reason='no_visible_acceleration_bias', fits=fits)
    corrected = []
    for ep, fit in zip((aa, bb), fits):
        if abs(ep['v']-fit['speed_mps']) > cfg['max_speed_adjustment_mps']:
            return dict(state='unavailable', reason='speed_adjustment_exceeds_evidence_gate', fits=fits)
        corrected.append(dict(ep, v=fit['speed_mps']))
    ca, cb = corrected
    result = refine(ca, cb, baseline(ca, cb), **params, smoothness=.01,
                    position_tolerance=0., speed_tolerance=0.)
    if result['state'] != 'candidate':
        result, _ = adaptive_retry(ca, cb, params)
    if result['state'] != 'candidate':
        return dict(state='unavailable', reason='corrected_endpoint_physics', fits=fits)
    points = result['points'].copy(); points[:, 1] *= sign
    return dict(state='candidate', points=points, method=VERSION, estimated=True,
                boundary_fits=fits, observed_endpoint_speed_mps=[a['v'], b['v']],
                estimated_endpoint_speed_mps=[sign*ca['v'], sign*cb['v']],
                exact_endpoint_position_interpolation=True,
                uncertainty='visible-regression retrospective estimate; not field-calibrated')
