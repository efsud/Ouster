"""Frozen spatial-mask proxy test for endpoint-local regime timing priors.

The 20/50/100 m bands are removed before grouping. This compares hypothetical
separated views of one sensor, where held-out identities can be scored. It does
not validate actual cross-sensor identities or estimate their clock offsets.
"""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import time

import numpy as np

from .corridor_campaign import subset, earlier_ids, atomic
from .validate_between_groups import cases
from .trajectory_regime_groups import TrajectoryRegimeGroups, RegimeConfig, VERSION as GROUPING_VERSION
from .regime_between_matching import annotate_endpoints, associate, VERSION
from .reconstruction_layers import prediction


def evaluate(snapshot, report, limit=60):
    records = []; details = []
    totals = {name: dict(eligible=0, correct=0, false=0, added_correct=0, added_false=0,
                        final_rejections=0, grouped_departures=0, grouped_arrivals=0,
                        anchor_matches=0, eligible_group_edges=0, position_errors_m=[])
              for name in ('baseline', 'regime_candidate')}
    for site, direction, width, rows in cases(snapshot, limit):
        for scenario in ('complete', 'missing_endpoints'):
            ai = [i for i, r in enumerate(rows) if scenario == 'complete' or int(r[0][8:16], 16) % 5]
            bi = [i for i, r in enumerate(rows) if scenario == 'complete' or int(r[0][16:24], 16) % 4][::-1]
            ls = dict(id=site['id'] + ':upstream', station_m=site['station_m'], tracks=[rows[i][4] for i in ai])
            rs = dict(id=site['id'] + ':downstream', station_m=site['station_m'], tracks=[rows[i][5] for i in bi])
            lg = TrajectoryRegimeGroups(ls).group(); rg = TrajectoryRegimeGroups(rs).group()
            left = annotate_endpoints([dict(rows[i][1], fragment=k) for k, i in enumerate(ai)], ls, lg)
            right = annotate_endpoints([dict(rows[i][2], fragment=k) for k, i in enumerate(bi)], rs, rg)
            for method, weight in [('baseline', 0), ('regime_candidate', .25)]:
                diag = {}
                matches = associate(left, right, report['calibration']['parameters'], weight=weight, diagnostics=diag)
                rec = dict(site=site['id'], direction=direction, width_m=width, scenario=scenario,
                    method=method, eligible=len(set(ai) & set(bi)), correct=0, false=0,
                    added_correct=0, added_false=0, final_rejections=0,
                    grouped_departures=sum(e['trajectory_group'] is not None for e in left),
                    grouped_arrivals=sum(e['trajectory_group'] is not None for e in right),
                    anchor_matches=diag.get('anchor_matches', 0), eligible_group_edges=diag.get('eligible_group_edges', 0))
                errors = []
                for match in matches:
                    i, j = ai[match['left']], bi[match['right']]
                    points = prediction(rows[i][1], rows[j][2], report, exact_join=True)
                    if points is None:
                        rec['final_rejections'] += 1
                        continue
                    correct = rows[i][0] == rows[j][0]
                    rec['correct' if correct else 'false'] += 1
                    if match.get('group_assistance'):
                        rec['added_correct' if correct else 'added_false'] += 1
                    error = None
                    if correct:
                        q = np.asarray(points); truth = rows[i][3]
                        error = float(np.mean(abs(np.interp(truth[:, 0], q[:, 0], q[:, 1]) - truth[:, 1])))
                        errors.append(error)
                    details.append(dict(site=site['id'], direction=direction, width_m=width,
                        scenario=scenario, method=method, departure_hash=rows[i][0], arrival_hash=rows[j][0],
                        correct=correct, group_assistance=bool(match.get('group_assistance')), position_mae_m=error))
                for key in totals[method]:
                    if key != 'position_errors_m':
                        totals[method][key] += rec[key]
                totals[method]['position_errors_m'].extend(errors)
                records.append(rec)
    for method, stats in totals.items():
        errors = stats.pop('position_errors_m')
        stats['position_mae_m'] = float(np.mean(errors)) if errors else None
        stats['p95_case_mae_m'] = float(np.quantile(errors, .95)) if errors else None
        stats['precision'] = stats['correct'] / max(1, stats['correct'] + stats['false'])
        extra = [m for m in details if m['method'] == method and m['group_assistance']]
        stats['added_correct_distinct_ids'] = len({(m['site'], m['departure_hash']) for m in extra if m['correct']})
        stats['added_false_distinct_ids'] = len({(m['site'], m['departure_hash']) for m in extra if not m['correct']})
        stats['sites_with_added_correct'] = sorted({m['site'] for m in extra if m['correct']})
    return dict(totals=totals, groups=records, matches=details)


def _qualified(result):
    base, new = result['totals']['baseline'], result['totals']['regime_candidate']
    return bool(new['correct'] > base['correct'] and new['false'] <= base['false'] and
                new['added_false'] == 0 and new['added_correct_distinct_ids'] >= 5 and
                len(new['sites_with_added_correct']) >= 3)


def run(source, report_path, output, limit=60):
    raw = Path(source).read_bytes(); snapshot = json.loads(raw)
    report = json.loads(Path(report_path).read_text())
    folder = Path(output); folder.mkdir(parents=True, exist_ok=True)
    duration = snapshot['end'] - snapshot['start']; boundary = duration / 2
    protocol = dict(created_at=time.time(), version=VERSION,
        source_sha256=hashlib.sha256(raw).hexdigest(), window=[snapshot['start'], snapshot['end']],
        split_absolute=snapshot['start'] + boundary, embargo_s=30, weight=.25,
        limit_per_mask_pool=limit, parameters=report['calibration']['parameters'],
        grouping_version=GROUPING_VERSION, grouping_config=asdict(RegimeConfig()),
        hidden_information_policy='Delete all hidden-band samples before segmentation and grouping; use observed-side lateral contexts only.',
        split_policy='Early half vs later half, 30-second embargo on each side; exclude later identities observed earlier.',
        decision_rule='Both partitions must add at least 5 distinct correct IDs across at least 3 sites, with no added false assignment. Fixed parameters; no later-set tuning.',
        test_opened=False)
    atomic(folder / 'protocol.json', protocol)
    early = subset(snapshot, 0, boundary - 30)
    later = subset(snapshot, boundary + 30, duration, earlier_ids(snapshot, boundary))
    validation = evaluate(early, report, limit); atomic(folder / 'validation.json', validation)
    print(json.dumps(dict(stage='validation', totals=validation['totals'])), flush=True)
    protocol.update(test_opened=True, validation_qualified=_qualified(validation), selection_frozen_at=time.time())
    atomic(folder / 'protocol.json', protocol)
    test = evaluate(later, report, limit); atomic(folder / 'test.json', test)
    deploy = _qualified(validation) and _qualified(test)
    result = dict(state='complete', protocol=protocol, validation=validation['totals'], test=test['totals'],
        deployment_eligible=deploy, qualification='spatial_mask_proxy_only', field_validated=False,
        limitations=['Separate-view masking inside a sensor is not actual cross-sensor identity validation.',
                     'Repeated widths/scenarios reuse vehicles; totals are not independent sample counts.',
                     'Unknown cross-sensor clocks and unobserved turning traffic remain unresolved.',
                     'A later half-hour is not an independent recording day.',
                     'Baseline anchors are hypotheses and group labels are sensor-local.'])
    atomic(folder / 'report.json', result)
    frozen_policy = dict(enabled=deploy, version=VERSION, validation_state='complete',
        parameters=protocol['parameters'], grouping_version=GROUPING_VERSION,
        grouping_config=protocol['grouping_config'], weight=.25, evidence=str(folder / 'report.json'))
    atomic(folder / 'policy.json', frozen_policy)
    print(json.dumps(dict(stage='complete', test=test['totals'], deployment_eligible=deploy)), flush=True)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--snapshot', required=True); parser.add_argument('--report', required=True)
    parser.add_argument('--output', required=True); parser.add_argument('--limit', type=int, default=60)
    args = parser.parse_args()
    run(args.snapshot, args.report, args.output, args.limit)
