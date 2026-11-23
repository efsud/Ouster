"""Fixed paired hidden-position test of moderate delivery-burst correction.

The same recorded positions are hidden under both time assignments. Selection
uses continuous candidate tracks and is conditional, not corridor-wide recall.
"""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import time
from unittest.mock import patch
import numpy as np
from .buffer_snapshot import copy_buffer
from .florida_rolling import build
from .moderate_delivery_timing import correct
from .delivery_timing import correct as baseline_correct
from .corridor_campaign import subset, earlier_ids, identity, atomic
from .spatial_bridges import endpoint
from .reconstruction_layers import prediction
from .reconstruction_study import summarize, metrics


def evaluate(snapshot, report, baseline_maps):
    cases = []
    for site in snapshot['sites']:
        pool = defaultdict(list)
        for tr in site['tracks']:
            if tr['class_type'] != '2':
                continue
            p = np.asarray(tr['points'], float).copy()
            if len(p) < 12 or np.any(np.diff(p[:, 0]) <= 0) or np.any(np.diff(p[:, 0]) > 1.5):
                continue
            receipts, baseline = baseline_maps[site['id']][tr['source_key'][0]]
            original = np.asarray(tr['original_receipt_offsets_s'])+snapshot['start']
            indexes = np.searchsorted(receipts, original)
            indexes = np.minimum(indexes, len(receipts)-1)
            previous = np.maximum(indexes-1, 0)
            indexes = np.where(abs(receipts[previous]-original) < abs(receipts[indexes]-original), previous, indexes)
            if np.max(abs(receipts[indexes]-original)) > 2e-6:
                continue
            baseline_times = baseline[indexes]-snapshot['start']
            rank = hashlib.sha256(identity(site, tr).encode()).hexdigest()
            for gap in (5, 10, 20):
                for fraction in (.25, .5, .75):
                    cut = p[0, 0]+(p[-1, 0]-p[0, 0]-gap)*fraction
                    i, j = np.searchsorted(p[:, 0], [cut, cut+gap])
                    if i < 4 or j+4 >= len(p) or j-i < 3:
                        continue
                    affected = np.max(abs(p[max(0, i-4):j+5, 0]-baseline_times[max(0, i-4):j+5])) > .1
                    pool[gap, bool(affected)].append((rank, tr, baseline_times, i, j))
        for (gap, affected), rows in sorted(pool.items()):
            for rank, tr, baseline_times, i, j in sorted(rows, key=lambda r: (r[0], r[3]))[:100]:
                p = np.asarray(tr['points'], float).copy()
                p[:, 1] *= 1 if tr['direction'] == 'eastbound' else -1
                old = p.copy()
                old[:, 0] = baseline_times
                row = dict(site=site['id'], identity_hash=rank, gap_s=gap, affected=affected, metrics={})
                for label, values in [('baseline', old), ('moderate', p)]:
                    a = endpoint(values[:i+1].tolist(), True)
                    b = endpoint(values[j:].tolist(), False)
                    if not a or not b or not 0 < b['t']-a['t'] <= 30:
                        continue
                    result = prediction(a, b, report, exact_join=True)
                    if result is not None:
                        row['metrics'][label] = metrics(np.asarray(result), values[i+1:j], report['calibration']['parameters'])
                cases.append(row)
    def summarize_cases(rows):
        common = [r for r in rows if len(r['metrics']) == 2]
        return dict(masks=len(rows), distinct_ids=len({r['identity_hash'] for r in rows}), common=len(common), common_distinct_ids=len({r['identity_hash'] for r in common}),
                    methods={label: dict(accepted=sum(label in r['metrics'] for r in rows),
                       quality=summarize([r['metrics'][label] for r in rows if label in r['metrics']]),
                       common=summarize([r['metrics'][label] for r in common])) for label in ('baseline', 'moderate')})
    return dict(summary={str(a): summarize_cases([r for r in cases if r['affected'] == a]) for a in (True, False)},
                sites={site['id']: {str(a): summarize_cases([r for r in cases if r['site'] == site['id'] and r['affected'] == a]) for a in (True, False)} for site in snapshot['sites']}, cases=cases)


def run(output):
    from dashboard.server import sites
    from .florida_rolling import geometry
    path = Path(output)
    path.mkdir(parents=True, exist_ok=True)
    db = copy_buffer('data/florida-rolling/buffer.sqlite3')
    end = db.execute('SELECT max(received) FROM frames').fetchone()[0]
    entries = [s for s in sites() if s['region'] == 'Florida']
    axes = json.load(open('config/reconstruction/corridor-road-axes.json'))
    site_order = iter(s['id'] for s in geometry(entries, axes))
    maps, checks = {}, []
    def adapter(rows):
        site_id = next(site_order)
        old, _ = baseline_correct(rows)
        new, audits = correct(rows)
        maps[site_id] = {}
        for session in {r[0] for r in old}:
            pairs = sorted((r[3], r[1]) for r in old if r[0] == session)
            # Duplicate delivery timestamps could select the wrong mapped
            # event. Reject this validation rather than silently choose one.
            if len({p[0] for p in pairs}) != len(pairs):
                raise ValueError('Ambiguous duplicate receipt timestamp in validation source')
            maps[site_id][session] = tuple(np.asarray(v) for v in zip(*pairs))
        preserved = sorted((r[0], r[3], r[2]) for r in new) == sorted(rows)
        checks.append(dict(site=site_id, rows=len(rows), original_rows_preserved=preserved,
                           additional_events=sum(len(a['events']) for a in audits['candidate']),
                           adjusted_frames=sum(a['additional_corrected_frames'] for a in audits['candidate'])))
        merged = []
        for base in audits['baseline']:
            extra = next(a for a in audits['candidate'] if a['session'] == base['session'])
            merged.append(dict(base, events=base['events']+extra['events'], moderate_additional_events=extra['events'],
                               corrected_frames=base['corrected_frames']+extra['additional_corrected_frames']))
        print('timing mapped', site_id, checks[-1], flush=True)
        return new, merged
    atomic(path/'protocol.json', dict(created_at=time.time(), window=[end-3600, end], embargo_s=30,
        selection='Continuous candidate car tracks; identical recorded hidden positions under both timelines; deterministic cap100 per site/gap/affected stratum',
        split='Earlier 1770s development; last1770s test excludes identities seen first1800s',
        candidate='Fixed .5<receipt step<=1.5 s, delay>=.25 s; production anchor/clock/delay/span constraints unchanged; no tuning',
        deployment_gate='>=20 affected test IDs, more accepted affected masks, common affected position/speed MAE not worse, unaffected MAE within .01m; no physics violations or changed raw rows'))
    try:
        with patch('deepctm.delivery_timing.correct', side_effect=adapter):
            snapshot = build(db, entries, end, road_axes=axes, time_basis='receipt_debursted', processing_interval_s=.5)
    finally:
        db.close()
    atomic(path/'row-checks.json', checks)
    atomic(path/'candidate-snapshot.json', snapshot)
    report = json.load(open('data/reconstruction/word-v1-collection/evaluation-001/report.json'))
    dev = evaluate(subset(snapshot, 0, 1770), report, maps)
    atomic(path/'development.json', dev)
    test = evaluate(subset(snapshot, 1830, 3600, earlier_ids(snapshot, 1800)), report, maps)
    atomic(path/'test.json', test)
    result = dict(state='complete', window=[snapshot['start'], snapshot['end']], development=dev['summary'], test=test['summary'],
                  test_by_site=test['sites'], rows=checks, status='candidate_not_deployed',
                  limitations=['Clock agreement is not independently measured event-time truth.', 'Selection is conditional on candidate-continuous tracks, not corridor-wide recall.',
                               'Repeated masks are correlated; no cross-sensor synchronization or identity verification.', 'No absent frames generated; raw positions and receipt timestamps preserved.'])
    atomic(path/'report.json', result)
    audit_gates(path)
    print(json.dumps(result), flush=True)


def audit_gates(output):
    """Report frozen gates; never deploy or retune on the evaluation results."""
    path = Path(output)
    def qualifies(rows):
        affected, unaffected = rows['True'], rows['False']
        before, after = affected['methods']['baseline'], affected['methods']['moderate']
        old, new = before['common'], after['common']
        return bool(affected['distinct_ids'] >= 20 and affected['common_distinct_ids'] >= 20
                    and after['accepted'] > before['accepted']
                    and new.get('mae_m', 1e9) <= old.get('mae_m', 0)
                    and new.get('speed_mae_mps', 1e9) <= old.get('speed_mae_mps', 0)
                    and after['quality'].get('physics_violation', 1) == 0
                    and unaffected['methods']['moderate']['common'].get('mae_m', 1e9)
                    <= unaffected['methods']['baseline']['common'].get('mae_m', 0)+.01)
    results, gates = {}, {}
    for partition in ('development', 'test'):
        result = json.loads((path/(partition+'.json')).read_text())
        for affected in (True, False):
            result['summary'][str(affected)]['common_distinct_ids'] = len({r['identity_hash'] for r in result['cases'] if r['affected'] == affected and len(r['metrics']) == 2})
            for site, rows in result['sites'].items():
                rows[str(affected)]['common_distinct_ids'] = len({r['identity_hash'] for r in result['cases'] if r['site'] == site and r['affected'] == affected and len(r['metrics']) == 2})
        atomic(path/(partition+'.json'), result)
        results[partition] = result
        gates[partition] = dict(aggregate=qualifies(result['summary']), sites={site: qualifies(rows) for site, rows in result['sites'].items()})
    evidence = json.loads((path/'report.json').read_text())
    evidence.update(development=results['development']['summary'], test=results['test']['summary'], test_by_site=results['test']['sites'],
                    gate_assessment=gates, aggregate_gate_pass=all(g['aggregate'] for g in gates.values()),
                    eligible_sites=[s for s in gates['test']['sites'] if all(g['sites'][s] for g in gates.values())],
                    gate_note='Requires20 distinct affected AND20 distinct commonly accepted identities in both partitions; per-site evidence also reported. No automatic deployment.',
                    status='candidate_not_deployed')
    pooled = {}
    for partition, result in results.items():
        rows = [r for r in result['cases'] if r['affected'] and r['site'] in evidence['eligible_sites']]
        common = [r for r in rows if len(r['metrics']) == 2]
        pooled[partition] = dict(affected_masks=len(rows), distinct_ids=len({r['identity_hash'] for r in rows}),
            common_masks=len(common), common_distinct_ids=len({r['identity_hash'] for r in common}),
            methods={name: dict(accepted=sum(name in r['metrics'] for r in rows),
                                common=summarize([r['metrics'][name] for r in common]),
                                quality=summarize([r['metrics'][name] for r in rows if name in r['metrics']]))
                     for name in ('baseline', 'moderate')})
    evidence['qualified_site_pooled'] = pooled
    atomic(path/'qualified-site-pooled.json', pooled)
    atomic(path/'report.json', evidence)
    return evidence


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    run(parser.parse_args().output)
