"""Predeclared development and later blind test of endpoint-time association.

CLI stages deliberately separate selection from opening a later test recording.
Identity-blind spatial masks are a same-sensor proxy, not cross-sensor truth.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time
from collections import Counter, defaultdict

import numpy as np

from .corridor_campaign import atomic, earlier_ids, identity, subset
from .endpoint_context_association import BASELINE, CANDIDATES, VERSION, associate, enrich
from .reconstruction_layers import prediction
from .validate_spatial import masked

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = ROOT/'data/reconstruction/word-v1-collection/evaluation-001/report.json'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_hashes():
    paths = ['endpoint_context_association.py', 'validate_endpoint_context_association.py',
             'bidirectional_association.py', 'global_association.py', 'spatial_bridges.py',
             'kinematic_gate.py', 'reconstruction_layers.py', 'matching_physics.py',
             'endpoint_context.py', 'endpoint_speed.py', 'object_shape.py',
             'validate_spatial.py', 'corridor_campaign.py']
    return {p: digest(ROOT/'deepctm'/p) for p in paths}


def mask_groups(snapshot, limit=80):
    groups = defaultdict(dict)
    for site in snapshot['sites']:
        for tr in site['tracks']:
            if tr.get('class_type') != '2' or tr.get('method'):
                continue
            p = np.asarray(tr['points'], float)
            if len(p) < 12 or not np.isfinite(p).all():
                continue
            ident = identity(site, tr)
            if ident is None:
                continue
            key = hashlib.sha256(ident.encode()).hexdigest()
            for width in (20, 50, 100):
                case = masked(tr, site['station_m'], width)
                if case is None:
                    continue
                a, b, truth = case[:3]
                a = enrich(dict(a, class_type='2'), p[p[:, 0] <= a['t']], True)
                b = enrich(dict(b, class_type='2'), p[p[:, 0] >= b['t']], False)
                # Original namespace exists only outside matcher input, for scoring.
                group = site['id'], tr['direction'], width
                groups[group].setdefault(key, (key, a, b, truth))
    output = {}
    for group, pool in groups.items():
        rows = sorted(pool.values(), key=lambda r: (r[1]['t'], r[0]))
        # One contiguous chronological block preserves dense competing traffic.
        first = max(0, (len(rows)-limit)//2)
        output[group] = rows[first:first+limit]
    return output


def totals(rows):
    out = {k: sum(r[k] for r in rows) for k in ('eligible', 'matched', 'correct', 'false', 'final_rejections')}
    correct_ids = {i for r in rows for i in r['correct_ids']}
    false_departures = {i for r in rows for i in r['false_departure_ids']}
    errors = [e for r in rows for e in r['errors_m']]
    out.update(correct_unique_ids=len(correct_ids), false_departure_unique_ids=len(false_departures),
               position_mae_m=float(np.mean(errors)) if errors else None,
               p95_case_mae_m=float(np.percentile(errors, 95)) if errors else None)
    return out


def evaluate(snapshot, report, modes, limit=80):
    rows = []; matches = []; global_diag = {m: Counter() for m in modes}
    for group, cases in sorted(mask_groups(snapshot, limit).items()):
        site_id, direction, width = group
        cache = {}
        for scenario in ('complete', 'missing_endpoints'):
            ai = [i for i, r in enumerate(cases) if scenario == 'complete' or int(r[0][8:16], 16) % 5]
            bi = [i for i, r in enumerate(cases) if scenario == 'complete' or int(r[0][16:24], 16) % 4]
            # Arrival input order supplies no same-index or FIFO shortcut.
            bi.reverse()
            left = [cases[i][1] for i in ai]; right = [cases[i][2] for i in bi]
            for mode in modes:
                cap = None if mode == 'baseline' else float(mode)
                diag = {}; proposed = associate(left, right, report['calibration']['parameters'],
                                                 cap_mps=cap, diagnostics=diag, **BASELINE)
                global_diag[mode].update(diag)
                correct_ids = []; false_ids = []; errors = []; accepted = 0; rejected = 0
                for match in proposed:
                    i, j = ai[match['left']], bi[match['right']]
                    if (i, j) not in cache:
                        cache[i, j] = prediction(cases[i][1], cases[j][2], report, exact_join=True)
                    path = cache[i, j]
                    if path is None:
                        rejected += 1; continue
                    accepted += 1; correct = cases[i][0] == cases[j][0]; error = None
                    if correct:
                        correct_ids.append(cases[i][0]); p = np.asarray(path); truth = cases[i][3]
                        error = float(np.mean(abs(np.interp(truth[:, 0], p[:, 0], p[:, 1])-truth[:, 1])))
                        errors.append(error)
                    else:
                        false_ids.append(cases[i][0])
                    matches.append(dict(site=site_id, direction=direction, width_m=width,
                        scenario=scenario, mode=mode, departure=cases[i][0], arrival=cases[j][0],
                        correct=correct, cost=match['cost'], margin=match['margin'], position_mae_m=error))
                rows.append(dict(site=site_id, direction=direction, width_m=width, scenario=scenario,
                    mode=mode, eligible=len(set(ai)&set(bi)), matched=accepted, correct=len(correct_ids),
                    false=len(false_ids), final_rejections=rejected, correct_ids=correct_ids,
                    false_departure_ids=false_ids, errors_m=errors))
        print(json.dumps(dict(site=site_id, direction=direction, width_m=width, cases=len(cases))), flush=True)
    summaries = {}
    for mode in modes:
        selected = [r for r in rows if r['mode'] == mode]
        summaries[mode] = dict(overall=totals(selected),
            by_width={str(w): totals([r for r in selected if r['width_m'] == w]) for w in (20, 50, 100)},
            by_scenario={s: totals([r for r in selected if r['scenario'] == s]) for s in ('complete', 'missing_endpoints')},
            by_direction={s: totals([r for r in selected if r['direction'] == s]) for s in ('eastbound', 'westbound')},
            by_site={s['id']: totals([r for r in selected if r['site'] == s['id']]) for s in snapshot['sites']})
    base = {(m['site'], m['direction'], m['width_m'], m['scenario'], m['departure'], m['arrival'])
            for m in matches if m['mode'] == 'baseline' and m['correct']}
    false_base = {(m['site'], m['direction'], m['width_m'], m['scenario'], m['departure'], m['arrival'])
                  for m in matches if m['mode'] == 'baseline' and not m['correct']}
    for mode in modes:
        added = [m for m in matches if m['mode'] == mode and m['correct'] and
                 (m['site'], m['direction'], m['width_m'], m['scenario'], m['departure'], m['arrival']) not in base]
        summaries[mode]['added_correct_unique_ids'] = len({m['departure'] for m in added})
        correct_keys = {(m['site'], m['direction'], m['width_m'], m['scenario'], m['departure'], m['arrival'])
                        for m in matches if m['mode'] == mode and m['correct']}
        false_keys = {(m['site'], m['direction'], m['width_m'], m['scenario'], m['departure'], m['arrival'])
                      for m in matches if m['mode'] == mode and not m['correct']}
        summaries[mode]['match_changes'] = {name: dict(cases=len(keys), unique_departure_ids=len({key[-2] for key in keys}))
            for name, keys in [('added_correct', correct_keys-base), ('lost_correct', base-correct_keys),
                               ('new_wrong', false_keys-false_base), ('resolved_wrong', false_base-false_keys)]}
    return dict(methods=summaries, groups=rows, matches=matches,
                diagnostics={k: dict(v) for k, v in global_diag.items()})


def qualifies(evaluation, mode, test=False):
    base, candidate = evaluation['methods']['baseline'], evaluation['methods'][mode]
    gain = candidate['overall']['correct']-base['overall']['correct']
    if gain < (5 if test else 1) or candidate['overall']['false'] > base['overall']['false']:
        return False
    if test and candidate['added_correct_unique_ids'] < 5:
        return False
    for field in ('by_width', 'by_scenario', 'by_site', 'by_direction'):
        if any(candidate[field][key]['false'] > before['false'] for key, before in base[field].items()):
            return False
    return True


def develop(snapshot_path, output, report_path=DEFAULT_REPORT):
    output = Path(output); output.mkdir(parents=True, exist_ok=False)
    raw = Path(snapshot_path).read_bytes(); snapshot = json.loads(raw)
    report = json.loads(Path(report_path).read_text())
    protocol = dict(version=VERSION, created_at=time.time(), source=str(Path(snapshot_path).resolve()),
        source_sha256=hashlib.sha256(raw).hexdigest(), source_hashes=source_hashes(),
        source_window=[snapshot['start'], snapshot['end']], development_range_s=[1800, 3540],
        training_range_s=[1800, 2640], validation_range_s=[2700, 3540], embargo_s=60,
        test_after_epoch=snapshot['end']+60, candidates=list(CANDIDATES), baseline=BASELINE,
        baseline_name='bidirectional_shape_v1', baseline_report=str(report_path), baseline_report_sha256=digest(report_path),
        parameters=report['calibration']['parameters'], widths_m=[20, 50, 100],
        scenarios=['complete', 'missing_endpoints'], max_per_site_direction_width=80,
        grouping='Each width/site/direction uses up to80 contiguous chronologically central identities, one case per ID.',
        identity_control='No identities enter matcher input. Entire validation IDs seen before offset2700 are excluded; test excludes every development snapshot ID and earlier test-window ID.',
        training='No fitted parameters. Earlier development portion audits candidate behavior; validation alone selects one of the two predeclared caps.',
        promotion='Validation: more correct matches, no more false overall/by width/by scenario/by site/by direction. Later test: same plus>=5 net correct and>=5 added distinct correct IDs.',
        revision_note='Revision002 fixes secondary-fit sampling cadence from prior development-only run; no held-out data opened. Prior artifacts retained.',
        unchanged_gates=['Movement exit/entry and direction filters; prior same-ID internal chain endpoints remain reserved in real application.',
            'No receipt-clock repair; projected overlap/sign conflicts remain rejected.',
            'Original endpoint median speeds retain reachability, exact feasible velocity and final prediction gates.',
            'Shape discrepancy, global partial one-to-one assignment, unmatched options and ambiguity margin unchanged.'],
        limitations=['Same-sensor spatial masking cannot establish actual cross-sensor identity or clock-offset accuracy.',
                    'Proxy hidden widths<=100m; real inter-sensor distances may approach350m.',
                    'Repeated widths/scenarios share identities; distinct-ID counts accompany case counts.'])
    atomic(output/'protocol.json', protocol)
    protocol_hash = digest(output/'protocol.json')
    training = subset(snapshot, 1800, 2640, earlier_ids(snapshot, 1800))
    validation = subset(snapshot, 2700, 3540, earlier_ids(snapshot, 2700))
    train_ids = {identity(s, tr) for s in training['sites'] for tr in s['tracks']}
    valid_ids = {identity(s, tr) for s in validation['sites'] for tr in s['tracks']}
    assert not train_ids & valid_ids
    atomic(output/'split_audit.json', dict(training_ids=len(train_ids), validation_ids=len(valid_ids), pairwise_overlap=0))
    modes = ['baseline', '1.0', '2.0']
    early = evaluate(training, report, modes); atomic(output/'training.json', early)
    reviewed = evaluate(validation, report, modes); atomic(output/'validation.json', reviewed)
    eligible = [m for m in modes[1:] if qualifies(reviewed, m)]
    selected = max(eligible, key=lambda m: (reviewed['methods'][m]['overall']['correct'], -float(m))) if eligible else None
    selection = dict(version=VERSION, protocol_sha256=protocol_hash, selected_cap_mps=float(selected) if selected else None,
        validation_qualified=bool(eligible), frozen_before_test_at=time.time(), source_hashes=source_hashes(),
        excluded_ids=earlier_ids(snapshot, float('inf')), methods=reviewed['methods'])
    atomic(output/'selection.json', selection)
    print(json.dumps(dict(state='selection_sealed', selected=selected,
        selection_sha256=digest(output/'selection.json'), methods=reviewed['methods'])), flush=True)
    return selection


def test(snapshot_path, output):
    output = Path(output)
    if (output/'test.json').exists():
        raise ValueError('This sealed test was already evaluated; do not retune on it')
    protocol = json.loads((output/'protocol.json').read_text()); selection = json.loads((output/'selection.json').read_text())
    if digest(output/'protocol.json') != selection['protocol_sha256'] or source_hashes() != selection['source_hashes']:
        raise ValueError('Protocol or source changed after selection')
    opened_at = time.time()
    if opened_at <= selection['frozen_before_test_at']:
        raise ValueError('Selection must be sealed before opening the test')
    raw = Path(snapshot_path).read_bytes(); snapshot = json.loads(raw)
    if hashlib.sha256(raw).hexdigest() == protocol['source_sha256']:
        raise ValueError('Development recording cannot be reused as held-out data')
    if snapshot['end'] <= protocol['source_window'][1]:
        raise ValueError('A later untouched capture is required')
    lo = max(0., protocol['test_after_epoch']-snapshot['start'])
    hi = snapshot['end']-snapshot['start']
    if hi-lo < 600:
        raise ValueError('At least ten minutes of later test recording required')
    opening = dict(opened_at=opened_at, heldout_sha256=hashlib.sha256(raw).hexdigest(),
                   selection_sha256=digest(output/'selection.json'), source=str(Path(snapshot_path).resolve()))
    if (output/'test_opening.json').exists():
        prior = json.loads((output/'test_opening.json').read_text())
        if (prior['heldout_sha256'] != opening['heldout_sha256'] or
                prior['selection_sha256'] != opening['selection_sha256']):
            raise ValueError('A different recording or selection cannot replace an opened test')
    else:
        atomic(output/'test_opening.json', opening)
    excluded = set(selection['excluded_ids']) | set(earlier_ids(snapshot, lo))
    holdout = subset(snapshot, lo, hi, excluded)
    test_ids = {identity(s, tr) for s in holdout['sites'] for tr in s['tracks']}
    assert not test_ids & excluded
    report = json.loads(Path(protocol['baseline_report']).read_text())
    if digest(protocol['baseline_report']) != protocol['baseline_report_sha256']:
        raise ValueError('Baseline parameters changed')
    # If development failed, a fixed cap1 diagnostic may run but cannot deploy.
    cap = selection['selected_cap_mps'] or 1.; mode = str(cap)
    result = evaluate(holdout, report, ['baseline', mode])
    atomic(output/'test.json', result)
    eligible = bool(selection['validation_qualified'] and qualifies(result, mode, test=True))
    summary = dict(state='complete', version=VERSION, deployment_eligible=eligible,
        selected_cap_mps=selection['selected_cap_mps'], tested_cap_mps=cap,
        protocol_sha256=digest(output/'protocol.json'), selection_sha256=digest(output/'selection.json'),
        heldout_sha256=hashlib.sha256(raw).hexdigest(), heldout_window_epoch=[snapshot['start']+lo,snapshot['start']+hi],
        heldout_unique_ids=len(test_ids), test_opened_after_selection=True, test_opened_at=opened_at,
        validation=selection['methods'], test=result['methods'],
        limitations=protocol['limitations'], unchanged_gates=protocol['unchanged_gates'])
    atomic(output/'report.json', summary)
    atomic(output/'policy.json', dict(enabled=eligible, version=VERSION, cap_mps=selection['selected_cap_mps'],
        validation_state='complete', baseline=BASELINE, parameters=protocol['parameters'],
        evidence=str(output/'report.json'), selection_sha256=digest(output/'selection.json')))
    print(json.dumps(summary), flush=True)
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=['develop', 'test']); parser.add_argument('--snapshot', required=True)
    parser.add_argument('--output', required=True); parser.add_argument('--report', default=str(DEFAULT_REPORT))
    args = parser.parse_args()
    if args.stage == 'develop':
        develop(args.snapshot, args.output, args.report)
    else:
        test(args.snapshot, args.output)
