"""Chronological, identity-disjoint recorded masking review of group gap priors."""
import argparse
import hashlib
import json
import time
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path

import numpy as np

from .corridor_campaign import atomic, earlier_ids, identity, subset
from .local_group_prior import DEFAULTS, prepare, predict
from .reconstruction_layers import prediction
from .reconstruction_study import masked_case, metrics, summarize


def _visible(track, a, b):
    points = [p for p in track['points'] if p[0] <= a['t'] or p[0] >= b['t']]
    return {k: track[k] for k in ('source_key', 'class_type', 'direction', 'lateral_start_m', 'lateral_end_m') if k in track} | dict(
        points=points, movement={'state': 'unknown'})


def _summary(rows, method):
    common = [r for r in rows if 'baseline' in r['metrics'] and method in r['metrics']]
    def stats(rr):
        return dict(n=len(rr), distinct_ids=len({r['identity_hash'] for r in rr}),
                    baseline=summarize([r['metrics']['baseline'] for r in rr]),
                    group=summarize([r['metrics'][method] for r in rr]))
    all_base = [r for r in rows if 'baseline' in r['metrics']]
    hybrid = [r['metrics'].get(method, r['metrics']['baseline']) for r in all_base]
    return dict(**stats(common), eligible=len(rows), baseline_accepted=len(all_base),
                group_accepted=sum(method in r['metrics'] for r in rows),
                fallback_included=dict(baseline=summarize([r['metrics']['baseline'] for r in all_base]), hybrid=summarize(hybrid)),
                per_site={site: stats([r for r in common if r['site'] == site]) for site in sorted({r['site'] for r in rows})},
                per_gap={str(gap): stats([r for r in common if r['gap_s'] == gap]) for gap in (5, 10, 20)})


def _qualifies(stats, min_ids=20):
    b, g = stats['baseline'], stats['group']
    return bool(stats['distinct_ids'] >= min_ids and g.get('mae_m', 1e9) <= .98*b.get('mae_m', 0)
                and g.get('speed_mae_mps', 1e9) <= 1.02*b.get('speed_mae_mps', 0)
                and g.get('p95_case_mae_m', 1e9) <= 1.02*b.get('p95_case_mae_m', 0)
                and g.get('physics_violation', 1) == 0)


def evaluate(part, report, weights, max_per_stratum=20):
    from .trajectory_groups import TrajectoryGroups
    rows = []; rejections = Counter()
    for site in part['sites']:
        clock = time.time(); groups = TrajectoryGroups(site)
        pool = defaultdict(list)
        for tr in site['tracks']:
            if tr.get('class_type') != '2' or tr.get('method'):
                continue
            rank = hashlib.sha256(identity(site, tr).encode()).hexdigest()
            for gap in (5, 10, 20):
                case = masked_case(tr, gap)
                if case is not None:
                    pool[tr['direction'], gap].append((rank, tr, gap, case))
        chosen = [item for group in pool.values() for item in sorted(group, key=lambda item: item[0])[:max_per_stratum]]
        for rank, tr, gap, (aa, bb, truth) in chosen:
            sign = 1 if tr['direction'] == 'eastbound' else -1
            a = dict(aa, x=sign*aa['x'], v=sign*aa['v'])
            b = dict(bb, x=sign*bb['x'], v=sign*bb['v'])
            row = dict(site=site['id'], identity_hash=rank, gap_s=gap, a_t=a['t'], b_t=b['t'], metrics={})
            base = prediction(a, b, report, exact_join=True)
            if base is not None:
                base = np.asarray(base); base[:, 1] *= sign
                row['metrics']['baseline'] = metrics(base, truth, report['calibration']['parameters'])
            visible = _visible(tr, a, b)
            prepared = prepare(site, visible, a, b, groups)
            row['group_state'] = prepared['state']
            if prepared['state'] != 'prepared':
                row['reason'] = prepared.get('reason'); rejections[row['reason']] += 1
            else:
                excluded = tuple(str(v) for v in tr['source_key'][:2])
                assert all(tuple(d) != excluded for d in prepared['donor_identities'])
                row.update(donor_count=prepared['donor_count'], group_id=prepared['group_id'],
                           consensus_spread_m=prepared['consensus_spread_m'])
                for weight in weights:
                    result = predict(prepared, report['calibration']['parameters'], weight)
                    name = str(weight)
                    if result['state'] == 'candidate':
                        points = result['points'].copy(); points[:, 1] *= sign
                        row['metrics'][name] = metrics(points, truth, report['calibration']['parameters'])
                    else:
                        rejections['solver_' + result['state']] += 1
            rows.append(row)
        print(json.dumps(dict(site=site['id'], cases=len(chosen), prepared=sum(r['site'] == site['id'] and r['group_state'] == 'prepared' for r in rows), elapsed_s=round(time.time()-clock, 2))), flush=True)
    return dict(cases=rows, rejections=dict(rejections), methods={str(w): _summary(rows, str(w)) for w in weights})


def run(snapshot, output, max_per_stratum=20):
    from .trajectory_groups import GroupConfig
    root = Path(__file__).resolve().parents[1]
    folder = Path(output); folder.mkdir(parents=True, exist_ok=False)
    raw = Path(snapshot).read_bytes(); s = json.loads(raw)
    # Preserve the exact test input while the rolling service continues running.
    (folder/'snapshot.json').write_bytes(raw)
    report = json.loads((root/'data/reconstruction/word-v1-collection/evaluation-001/report.json').read_text())
    half = (s['end']-s['start'])/2
    protocol = dict(created_at=time.time(), snapshot_sha256=hashlib.sha256(raw).hexdigest(),
        source_window=[s['start'], s['end']], split_offset_s=half, embargo_s=30,
        configuration=DEFAULTS, group_configuration=asdict(GroupConfig()), candidate_weights=[.25, .5, 1.], masks_s=[5, 10, 20],
        maximum_per_site_direction_gap=max_per_stratum,
        sampling='SHA256 of local identity; full continuous trajectories only',
        leakage_controls=['No hidden target samples passed to grouping/classification/prediction.',
            'All same sensor/session/object-ID fragments excluded before grouping and from donor fit.',
            'Direction is observed; movement withheld from target membership; endpoint lateral values are visible.',
            'Test identities previously observed before split removed, including all their fragments.',
            'Donor groups are computed separately inside each chronological partition.',
            'Donor shift/offset uses only the four visible seconds on each side; no hidden-target loss.',
            'Weight selected on development and frozen before test scoring.'],
        promotion_gate='At least 20 common distinct test IDs globally and 10 at a site; >=2% position-MAE improvement, speed and p95 case MAE no more than 2% worse, zero physics violations. Site must qualify in development and test.',
        test_opened=False)
    atomic(folder/'protocol.json', protocol)
    dev = evaluate(subset(s, 0, half-30), report, [.25, .5, 1.], max_per_stratum)
    atomic(folder/'development.json', dev)
    candidates = [w for w in (.25, .5, 1.) if _qualifies(dev['methods'][str(w)])]
    # Even a failed candidate is tested once for an honest review, never promoted.
    # Candidate solvers can abstain on different cases. Compare the SAME whole
    # baseline-accepted development set with baseline fallback on every abstention.
    choice = min(candidates or [.25, .5, 1.], key=lambda w: dev['methods'][str(w)]['fallback_included']['hybrid'].get('mae_m', 1e9))
    protocol.update(selected_weight=choice, selection_qualified=bool(candidates), test_opened=True, frozen_at=time.time())
    atomic(folder/'protocol.json', protocol)
    test = evaluate(subset(s, half+30, s['end']-s['start'], earlier_ids(s, half)), report, [choice], max_per_stratum)
    atomic(folder/'test.json', test)
    d, t = dev['methods'][str(choice)], test['methods'][str(choice)]
    approved = [site for site in t['per_site'] if _qualifies(t['per_site'][site], 10) and _qualifies(d['per_site'][site], 10)]
    eligible = bool(candidates and _qualifies(t) and approved)
    result = dict(state='complete', protocol=protocol, development=d, test=t,
        selected_weight=choice, enabled_sites=approved if eligible else [],
        deployment_eligible=eligible,
        rejections=dict(development=dev['rejections'], test=test['rejections']),
        limitations=['Known same-object temporal masking only; this does not validate changed-ID associations or inter-sensor identity.',
            'Group peers are contemporaneous observations, not known same-lane leaders; this is retrospective reconstruction, not a live future forecast.',
            'Repeated 5/10/20-second masks can reuse a vehicle and are not independent observations.',
            'Donor-supported cases and all-case fallback errors are both reported to avoid abstention bias.',
            'One rolling hour and provisional calibration cannot establish field validation or KPI accuracy.',
            'Unsupported groups and gaps stay unresolved or use the separately validated existing estimator.'])
    atomic(folder/'report.json', result)
    atomic(folder/'policy.json', dict(version='trajectory_group_peer_shape_v1', enabled=eligible,
        enabled_sites=result['enabled_sites'], weight=choice, configuration=DEFAULTS,
        parameters=report['calibration']['parameters'], group_configuration=asdict(GroupConfig()), validation_state='complete',
        evidence=str(folder/'report.json'), snapshot_sha256=protocol['snapshot_sha256']))
    print(json.dumps(result), flush=True)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--snapshot', default='data/florida-rolling/snapshot.json')
    parser.add_argument('--output', required=True); parser.add_argument('--max-per-stratum', type=int, default=20)
    args = parser.parse_args(); run(args.snapshot, args.output, args.max_per_stratum)
