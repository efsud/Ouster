"""Guarded opt-in production adapter for the validated local boundary retry.

Existing estimates and observations are retained unchanged. Only still-missing,
already-admissible same-session/object car gaps in the exact qualified site and
actual-duration scope may receive an additional estimated path.
"""
import hashlib
import inspect
import json
from pathlib import Path
import time

from .instantaneous_boundary_retry import VERSION, established_prediction, reconstruct
from .reconstruction_layers import prediction
from .same_id_gaps import candidates


def _qualified(policy, report):
    if (not policy or not policy.get('enabled') or policy.get('version') != VERSION or
        policy.get('validation_state') != 'complete' or
        report.get('selected_method') != 'kinematic_0.01' or
        policy.get('parameters') != report.get('calibration', {}).get('parameters') or
        not policy.get('runtime_site_scopes') or not policy.get('evidence')):
        return False, 'policy_not_qualified'
    try:
        evidence_path=Path(policy['evidence'])
        if not evidence_path.is_absolute():
            evidence_path=Path(__file__).resolve().parents[1]/evidence_path
        folder=evidence_path.parent
        reviewed=json.loads(evidence_path.read_text())
        selected_bytes=(folder/'selection.json').read_bytes()
        selected=json.loads(selected_bytes)
        protocol_bytes=(folder/'protocol.json').read_bytes()
        protocol=json.loads(protocol_bytes)
        scope_bytes=(folder/'deployment-scope.json').read_bytes()
        scoped=json.loads(scope_bytes)
        if (not reviewed.get('deployment_eligible') or
            hashlib.sha256(selected_bytes).hexdigest()!=policy.get('selection_sha256') or
            hashlib.sha256(protocol_bytes).hexdigest()!=selected.get('protocol_sha256') or
            selected['configuration']!=policy.get('configuration') or
            protocol.get('implementation_sha256')!=policy.get('implementation_sha256') or
            protocol.get('baseline_configuration')!=policy.get('baseline_configuration') or
            protocol.get('parameters')!=policy.get('parameters') or
            hashlib.sha256(scope_bytes).hexdigest()!=policy.get('deployment_scope_sha256') or
            scoped['scopes']!=policy['runtime_site_scopes'] or
            policy.get('enabled_site_duration_bands')!=reviewed.get('enabled_site_duration_bands') or
            set(policy.get('enabled_sites',[]))-set(reviewed.get('enabled_sites',[]))):
            return False, 'frozen_validation_or_runtime_scope_changed'
    except (OSError,ValueError,KeyError,TypeError):
        return False, 'validation_evidence_missing'
    from .validate_instantaneous_boundary import baseline_configuration
    try:
        if policy.get('baseline_configuration') != baseline_configuration():
            return False, 'baseline_policy_changed'
    except (AssertionError, OSError, KeyError, ValueError):
        return False, 'baseline_policy_unavailable_or_changed'
    # Integration changes the surrounding worker file, not its baseline
    # prediction function. Other frozen predictor/helpers must match bytewise.
    expected = policy.get('implementation_sha256', {})
    if not expected or policy.get('baseline_prediction_sha256') != hashlib.sha256(inspect.getsource(prediction).encode()).hexdigest():
        return False, 'baseline_prediction_changed'
    directory = Path(__file__).resolve().parent
    for name, signature in expected.items():
        if name == 'reconstruction_layers.py':
            continue
        path = directory/name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != signature:
            return False, 'frozen_implementation_changed'
    return True, None


def _in_scope(site_id, duration, policy):
    if site_id not in policy.get('enabled_sites', []):
        return False
    bands = policy.get('enabled_site_duration_bands', {}).get(site_id, [])
    if not any(lo < duration <= hi+1e-8 for lo, hi in bands):
        return False
    return any(float(scope['minimum_exclusive_s']) < duration <= float(scope['maximum_inclusive_s'])+1e-8
               for scope in policy.get('runtime_site_scopes', {}).get(site_id, []))


def apply(snapshot, layers, report, policy, max_attempts=40, max_seconds=5.):
    """Append qualified missing local estimates; never overwrite existing data."""
    output = dict(layers)
    local = list(layers.get('within_intersection', [])); output['within_intersection'] = local
    audit = dict(state='disabled', attempted=0, added=0, existing_preserved=len(local), reasons={})
    output['instantaneous_boundary_review'] = audit
    qualified, reason = _qualified(policy, report)
    if not qualified:
        audit['reason'] = reason
        return output
    started = time.monotonic(); audit['state'] = 'evaluated'
    for original_site in snapshot.get('sites', []):
        site_id = original_site['id']
        if site_id not in policy.get('runtime_site_scopes', {}):
            continue
        tracks = [tr for tr in original_site['tracks'] if not tr.get('method') and
                  tr.get('source') not in ('inferred','estimated','simulated')]
        site = dict(original_site, tracks=tracks)
        fragments = {}
        for tr in tracks:
            key = tr.get('source_key', [])
            if len(key) == 3:
                fragments.setdefault(tuple(key[:2]), []).append(tr)
        for pair in candidates(site, include_same_class=True,
                               allow_stationary_noise=site_id != 'OBC-AG-SA-C257223'):
            if audit['attempted'] >= max_attempts or time.monotonic()-started >= max_seconds:
                audit['budget_exhausted'] = True
                break
            a,b = pair['a'],pair['b']; duration = b['t']-a['t']
            if not _in_scope(site_id,duration,policy) or any(str(c) != '2' for c in pair['classes']):
                continue
            key = tuple(pair['identity'])
            # Any existing same-identity inferred interval overlapping this gap
            # is preserved; the retry does not replace a partially filled path.
            if any(p.get('site') == site_id and tuple(p.get('identity_key', [])[:2]) == key and
                   p.get('points') and min(b['t'],p['points'][-1][0])-max(a['t'],p['points'][0][0]) > 1e-7
                   for p in local):
                continue
            possibilities = fragments.get(key, [])
            before = next((tr for tr in possibilities if abs(tr['points'][-1][0]-a['t']) < 1e-7 and
                           abs(tr['points'][-1][1]-a['x']) < 1e-7),None)
            after = next((tr for tr in possibilities if abs(tr['points'][0][0]-b['t']) < 1e-7 and
                          abs(tr['points'][0][1]-b['x']) < 1e-7),None)
            if before is None or after is None:
                continue
            if any(a['t']+1e-7 < p[0] < b['t']-1e-7 for tr in possibilities for p in tr['points']):
                continue
            base = established_prediction(site_id,a,b,report,pair['classes'],pair.get('stationary_noise_admission',False))
            if base is not None:
                audit['reasons']['baseline_already_feasible'] = audit['reasons'].get('baseline_already_feasible',0)+1
                continue
            audit['attempted'] += 1
            proposal = reconstruct(site_id,before['points'],after['points'],a,b,pair['direction'],report,
                                   policy['configuration'],pair['classes'],established=None)
            if proposal['state'] != 'candidate':
                why = proposal.get('reason',proposal['state'])
                audit['reasons'][why] = audit['reasons'].get(why,0)+1
                continue
            local.append({k:v for k,v in proposal.items() if k not in ('state','points')} | dict(
                points=proposal['points'].tolist(),site=site_id,direction=pair['direction'],class_type='2',
                identity_key=list(key),object_id=key[1],identity='same_sensor_session_id_boundary_retry',
                endpoint_classes=pair['classes'],source='inferred',gap_s=duration,
                gap_kind='recording_interruption' if pair['recording_gap'] else 'same_id_fragment_break',
                frame_gap_basis=pair['frame_gap_basis'],missing_receipt_fraction=pair['missing_receipt_fraction'],
                estimation_model=VERSION,validation_report=policy['evidence'],
                endpoint_speed_basis='estimated instantaneous derivative of visible one-sided quadratic fit',
                baseline_provenance='Existing full physical baseline rejected; identity/clock/movement/lateral admission retained'))
            audit['added'] += 1
    audit['elapsed_s'] = round(time.monotonic()-started,3)
    return output
