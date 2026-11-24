"""Frozen three-way recorded-data review of local regime-conditioned learning."""
import argparse
import hashlib
import json
import time
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path

import numpy as np

from .corridor_campaign import atomic, earlier_ids, identity, subset
from .local_group_prior import DEFAULTS, prepare as old_prepare, predict as peer_predict
from .reconstruction_layers import prediction
from .reconstruction_study import metrics, summarize
from .regime_group_learning import VERSION, features, fit, prepare, predict, training_label
from .spatial_bridges import endpoint
from .trajectory_groups import TrajectoryGroups
from .validate_local_group_prior import _visible


def masks(track, seconds):
    """Deterministic masks from continuous measured runs, one per local regime.

    Regime labels stratify the benchmark only. They are never prediction inputs.
    A mask's complete target identity is excluded from all peer discovery.
    """
    p = np.asarray(track['points'], float)
    if p.ndim != 2 or p.shape[1] < 3 or not np.all(np.isfinite(p[:, :3])):
        return []
    sign = 1 if track['direction'] == 'eastbound' else -1
    cuts = np.flatnonzero((np.diff(p[:, 0]) > 1.5) | (np.diff(p[:, 0]) <= 0))+1
    found = {}
    for run in np.split(p[:, :3], cuts):
        if len(run) < 15 or run[-1, 0]-run[0, 0] < seconds+8:
            continue
        oriented = run.copy(); oriented[:, 1] *= sign
        # Fixed five-second center stride: not chosen to flatter a predictor.
        for start in np.arange(run[0, 0]+4, run[-1, 0]-seconds-4+.001, 5.):
            i = int(np.searchsorted(run[:, 0], start))
            j = int(np.searchsorted(run[:, 0], run[i, 0]+seconds, side='right')-1)
            if j-i < 3 or i < 5 or len(run)-j < 5:
                continue
            a, b = endpoint(oriented[:i+1], True), endpoint(oriented[j:], False)
            if a is None or b is None or min(a['v'], b['v']) < 0 or b['x'] < a['x']:
                continue
            truth = oriented[i+1:j]
            regime = ('stopped' if np.max(truth[:, 2]) < .5 else
                      'moving' if np.min(truth[:, 2]) >= 1. else 'transition')
            if regime not in found:
                found[regime] = (a, b, truth)
    return [(regime, case) for regime, case in found.items()]


def summary(rows, method):
    base = [r for r in rows if 'kinematic' in r['metrics']]
    common = [r for r in base if method in r['metrics']]
    supported = [r for r in rows if method in r['metrics']]
    def stat(selected):
        return dict(n=len(selected), independent_ids=len({r['identity_hash'] for r in selected}),
                    kinematic=summarize([r['metrics']['kinematic'] for r in selected]),
                    candidate=summarize([r['metrics'][method] for r in selected]))
    return dict(eligible=len(rows), eligible_ids=len({r['identity_hash'] for r in rows}),
                kinematic_accepted=len(base), candidate_accepted=len(supported),
                candidate_ids=len({r['identity_hash'] for r in supported}),
                common=stat(common), fallback_count=sum(method not in r['metrics'] for r in base),
                fallback_included=dict(n=len(base), independent_ids=len({r['identity_hash'] for r in base}),
                    kinematic=summarize([r['metrics']['kinematic'] for r in base]),
                    candidate=summarize([r['metrics'].get(method, r['metrics']['kinematic']) for r in base])),
                per_site={s: stat([r for r in common if r['site'] == s]) for s in sorted({r['site'] for r in rows})},
                per_gap={str(g): stat([r for r in common if r['gap_s'] == g]) for g in (5, 10, 20)},
                per_regime={s: stat([r for r in common if r['regime'] == s]) for s in ('stopped', 'moving', 'transition')},
                site_coverage={s: dict(eligible=sum(r['site'] == s for r in rows),
                     accepted=sum(r['site'] == s for r in supported),
                     independent_ids=len({r['identity_hash'] for r in supported if r['site'] == s}))
                     for s in sorted({r['site'] for r in rows})})


def evaluate(part, report, phase, max_per_stratum=4, models=None, archive=None):
    from .trajectory_regime_groups import TrajectoryRegimeGroups
    rows, prepared_cache, reasons = [], {}, Counter()
    params = report['calibration']['parameters']
    for site in part['sites']:
        started = time.monotonic()
        old_groups, new_groups = TrajectoryGroups(site), TrajectoryRegimeGroups(site)
        pools = defaultdict(dict)
        for track in site['tracks']:
            if track.get('class_type') != '2' or track.get('method'):
                continue
            rank = hashlib.sha256(identity(site, track).encode()).hexdigest()
            for gap in (5, 10, 20):
                for regime, case in masks(track, gap):
                    pools[track['direction'], gap, regime].setdefault(rank, (rank, track, gap, regime, case))
        selected = [item for pool in pools.values() for _, item in sorted(pool.items())[:max_per_stratum]]
        for rank, track, gap, regime, (aa, bb, truth) in selected:
            sign = 1 if track['direction'] == 'eastbound' else -1
            a, b = dict(aa, x=sign*aa['x'], v=sign*aa['v']), dict(bb, x=sign*bb['x'], v=sign*bb['v'])
            row = dict(site=site['id'], identity_hash=rank, gap_s=gap, actual_gap_s=b['t']-a['t'],
                       regime=regime, direction=track['direction'], a_t=a['t'], b_t=b['t'], metrics={}, states={})
            base = prediction(a, b, report, exact_join=True)
            if base is not None:
                p = np.asarray(base); p[:, 1] *= sign
                row['metrics']['kinematic'] = metrics(p, truth, params)
            visible = _visible(track, a, b)
            old = old_prepare(site, visible, a, b, old_groups)
            current = prepare(site, visible, a, b, new_groups)
            for method, prepared in [('whole_track_peer', old), ('regime_fixed', current)]:
                row['states'][method] = prepared['state']
                if prepared['state'] != 'prepared':
                    reasons[method+':'+prepared.get('reason', 'unknown')] += 1
                    continue
                excluded = tuple(str(v) for v in track['source_key'][:2])
                assert all(tuple(v) != excluded for v in prepared['donor_identities'])
                r = peer_predict(prepared, params, .5)
                row['states'][method] = r['state']
                if r['state'] == 'candidate':
                    p = r['points'].copy(); p[:, 1] *= sign
                    row['metrics'][method] = metrics(p, truth, params)
                else:
                    reasons[method+':solver_'+r['state']] += 1
            if current['state'] == 'prepared':
                row.update(features=features(current).tolist(), donor_count=current['donor_count'],
                           donor_ids_hash=[hashlib.sha256(json.dumps([site['id'], d]).encode()).hexdigest()
                                           for d in current['donor_identities']],
                           group_id=current['group_id'])
                if phase == 'training':
                    row['target_weight'] = training_label(current, truth)
                prepared_cache[len(rows)] = (current, truth, sign)
                for name, model in (models or {}).items():
                    learned = predict(current, params, model)
                    row['states'][name] = learned['state']
                    if learned['state'] == 'candidate':
                        p = learned['points'].copy(); p[:, 1] *= sign
                        row['metrics'][name] = metrics(p, truth, params)
                        row.setdefault('weights', {})[name] = learned['learned_weight']
                    else:
                        reasons[name+':'+learned.get('reason', learned['state'])] += 1
                if archive is not None:
                    serialized = {**current, 'reference': current['reference'].tolist()}
                    archive.write(json.dumps(dict(phase=phase, row_index=len(rows), site=site['id'],
                        identity_hash=rank, visible=visible, a=a, b=b, prepared=serialized,
                        truth=truth.tolist()), allow_nan=False)+'\n')
            rows.append(row)
        print(json.dumps(dict(phase=phase, site=site['id'], eligible=len(selected),
            regime_prepared=sum(r['site']==site['id'] and 'features' in r for r in rows),
            elapsed_s=round(time.monotonic()-started, 2))), flush=True)
    methods = ['whole_track_peer', 'regime_fixed']+list(models or {})
    return dict(cases=rows, reasons=dict(reasons), methods={name: summary(rows, name) for name in methods}), prepared_cache


def qualifies(stat, minimum=20):
    common = stat.get('common', stat)
    b, n = common['kinematic'], common['candidate']
    return bool(common['independent_ids'] >= minimum and n.get('mae_m', 1e9) <= .98*b.get('mae_m', 0)
                and n.get('speed_mae_mps', 1e9) <= 1.02*b.get('speed_mae_mps', 0)
                and n.get('p95_case_mae_m', 1e9) <= 1.02*b.get('p95_case_mae_m', 0)
                and n.get('physics_violation', 1) == 0)


def run(snapshot, output, max_per_stratum=4):
    from .trajectory_regime_groups import RegimeGroupConfig
    root = Path(__file__).resolve().parents[1]
    folder = Path(output); folder.mkdir(parents=True, exist_ok=False)
    raw = Path(snapshot).read_bytes(); s = json.loads(raw)
    report = json.loads((root/'data/reconstruction/word-v1-collection/evaluation-001/report.json').read_text())
    duration = s['end']-s['start']; first, second = .5*duration, .75*duration
    protocol = dict(version=VERSION, source=str(Path(snapshot).resolve()),
        snapshot_sha256=hashlib.sha256(raw).hexdigest(), recorded_window=[s['start'], s['end']],
        split_offsets_s=[0, first, second, duration], embargo_s=30, masks_s=[5, 10, 20],
        regimes=['stopped', 'moving', 'transition'], candidate_ridge=[1., 10., 100.],
        minimum_training_ids=20, maximum_per_site_direction_gap_regime=max_per_stratum,
        fixed_peer_weight=.5, configuration=DEFAULTS, group_configuration=asdict(RegimeGroupConfig()),
        parameters=report['calibration']['parameters'], created_at=time.time(),
        sampling='Fixed five-second centers in continuous observed runs; earliest mask per identity/gap/regime; SHA256 identity ranking within strata.',
        leakage_controls=['All target-ID fragments excluded before grouping, including classification changes.',
            'Hidden target samples removed before local group membership and visible donor alignment.',
            'Only training hidden values generate learning labels. Normalization and ridge fitting use training only.',
            'Validation selects regularization before test scoring; selection hash is sealed before test.',
            'Validation IDs seen in training and test IDs seen before test boundary are excluded.',
            'Each split discovers peer groups separately. Contemporaneous donors are allowed for retrospective reconstruction.',
            'Hidden regime labels are used only for benchmark stratification, never as model features.'],
        promotion_gate='At least 20 independent common IDs globally and 10 per enabled site in both validation and test; >=2% position MAE gain; speed and p95 position error at most2% worse; zero physics violations; learned all-baseline-case fallback position MAE no worse than both fixed peer alternatives.',
        scope='Passenger vehicle class2 local same-ID temporal masks; no cross-intersection identity claim.')
    atomic(folder/'protocol.json', protocol)
    protocol_hash = hashlib.sha256((folder/'protocol.json').read_bytes()).hexdigest()
    train = subset(s, 0, first-30)
    validation = subset(s, first+30, second-30, earlier_ids(s, first))
    testing = subset(s, second+30, duration, earlier_ids(s, second))
    idsets = [{identity(site, tr) for site in part['sites'] for tr in site['tracks']}
              for part in (train, validation, testing)]
    assert not (idsets[0]&idsets[1] or idsets[0]&idsets[2] or idsets[1]&idsets[2])
    atomic(folder/'split_audit.json', dict(independent_ids=[len(v) for v in idsets],
         pairwise_overlap=[len(idsets[0]&idsets[1]), len(idsets[0]&idsets[2]), len(idsets[1]&idsets[2])]))
    with (folder/'training_prepared.jsonl').open('w') as archive:
        training, _ = evaluate(train, report, 'training', max_per_stratum, archive=archive)
    atomic(folder/'training.json', training)
    models = {str(r): fit(training['cases'], r) for r in protocol['candidate_ridge']}
    atomic(folder/'candidate_models.json', models)
    with (folder/'validation_prepared.jsonl').open('w') as archive:
        valid, _ = evaluate(validation, report, 'validation', max_per_stratum, models, archive)
    atomic(folder/'validation.json', valid)
    eligible_models = [name for name in models if models[name]['state']=='trained' and qualifies(valid['methods'][name])]
    trained = [name for name in models if models[name]['state']=='trained']
    selected = min(eligible_models or trained or models, key=lambda name:
        valid['methods'][name]['fallback_included']['candidate'].get('mae_m', 1e9))
    chosen = models[selected]
    selection = dict(protocol_sha256=protocol_hash, selected_ridge=selected, model=chosen,
                     validation_qualified=bool(eligible_models), frozen_before_test_at=time.time())
    atomic(folder/'selection.json', selection)
    selection_hash = hashlib.sha256((folder/'selection.json').read_bytes()).hexdigest()
    with (folder/'test_prepared.jsonl').open('w') as archive:
        test, _ = evaluate(testing, report, 'test', max_per_stratum, {'learned_regime': chosen}, archive)
    atomic(folder/'test.json', test)
    # Deterministic earliest accepted example in each regime, selected by time
    # rather than by low error. Show actual hidden truth for audit, not as input.
    chosen_examples = {}
    for index, row in sorted(enumerate(test['cases']), key=lambda item: (item[1]['a_t'], item[1]['site'], item[0])):
        if 'learned_regime' in row['metrics']:
            chosen_examples.setdefault(row['regime'], index)
    examples = []
    for line in (folder/'test_prepared.jsonl').read_text().splitlines():
        case = json.loads(line)
        if case['row_index'] not in chosen_examples.values():
            continue
        prepared = case['prepared']; prepared['reference'] = np.asarray(prepared['reference'])
        learned = predict(prepared, report['calibration']['parameters'], chosen)
        sign = prepared['sign']; truth = np.asarray(case['truth']); truth[:, 1] *= sign
        row = test['cases'][case['row_index']]
        examples.append(dict(site=case['site'], regime=row['regime'], identity_hash=case['identity_hash'],
            gap_s=row['gap_s'], metrics=row['metrics'], visible=case['visible']['points'],
            hidden_truth=truth.tolist(), learned=learned['points'].tolist(),
            a=case['a'], b=case['b'], learned_weight=learned['learned_weight'],
            selection='earliest accepted held-out example per regime, not selected by error'))
    atomic(folder/'examples.json', dict(recording_start=s['start'], examples=examples))
    v, t = valid['methods'][selected], test['methods']['learned_regime']
    enabled_sites = [site for site in t['per_site'] if qualifies(v['per_site'][site], 10) and qualifies(t['per_site'][site], 10)]
    wins_alternatives = all(t['fallback_included']['candidate'].get('mae_m', 1e9) <=
        test['methods'][alternative]['fallback_included']['candidate'].get('mae_m', 1e9)
        for alternative in ('whole_track_peer', 'regime_fixed'))
    eligible = bool(eligible_models and qualifies(t) and enabled_sites and wins_alternatives)
    result = dict(state='complete', version=VERSION, protocol_sha256=protocol_hash,
        selection_sha256=selection_hash, training_samples=chosen.get('samples', 0),
        training_independent_ids=chosen.get('independent_ids', 0), selected_ridge=selected,
        validation_methods=valid['methods'], test_methods=test['methods'],
        deployment_eligible=eligible, enabled_sites=enabled_sites if eligible else [],
        selection_validation_qualified=bool(eligible_models), beats_fixed_alternatives=wins_alternatives,
        limitations=['One frozen hour, provisional geometry and receipt time; not field-validated KPI accuracy.',
            'Recorded masking validates local shape reconstruction, not changed-ID or cross-intersection associations.',
            'Contemporaneous peers use observations after the gap; retrospective estimates are not real-time forecasts.',
            'Multiple gap lengths/regimes can reuse vehicles; independent IDs and full fallback denominator are reported.',
            'Screenshot purple markings are qualitative guidance; the exact screenshot window expired from retention.',
            'Sparse supported groups must abstain. This method cannot promise every missing trajectory.'])
    atomic(folder/'report.json', result)
    atomic(folder/'policy.json', dict(version=VERSION, enabled=eligible, enabled_sites=result['enabled_sites'],
        configuration=DEFAULTS, group_configuration=asdict(RegimeGroupConfig()),
        parameters=report['calibration']['parameters'], model=chosen, validation_state='complete',
        evidence=str(folder/'report.json'), snapshot_sha256=protocol['snapshot_sha256']))
    print(json.dumps(dict(state='complete', output=str(folder), deployment_eligible=eligible,
          training_ids=chosen.get('independent_ids'), test=t)), flush=True)
    return result


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--snapshot', required=True); parser.add_argument('--output', required=True)
    parser.add_argument('--max-per-stratum', type=int, default=4)
    args=parser.parse_args(); run(args.snapshot, args.output, args.max_per_stratum)
