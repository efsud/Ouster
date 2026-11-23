"""Paired same-sensor spatial masks for approved moderate-timing sites only."""
import json
from pathlib import Path
import numpy as np
from .corridor_campaign import atomic, subset, earlier_ids
from .validate_delivery_matching import evaluate


def run(output='data/reconstruction/moderate-delivery-validation'):
    folder = Path(output)
    snapshot = json.loads((folder/'candidate-snapshot.json').read_text())
    report = json.loads((folder/'report.json').read_text())
    approved = set(report['eligible_sites'])
    params = json.load(open('data/reconstruction/word-v1-collection/evaluation-001/report.json'))['calibration']['parameters']
    atomic(folder/'matching-protocol.json', dict(window=[snapshot['start'], snapshot['end']], enabled_sites=sorted(approved),
        baseline_reconstruction='Only additional moderate-burst intervals had untouched baseline receipt times; restore original receipt there, retain prior correction elsewhere. Round both to production0.01s plotting precision.',
        masks='Fixed same recorded rows, spatial widths20/50/100m; full/missing-arrival scenarios; chronological split30s embargo+early-ID exclusion.',
        gate='No increase in wrong identities and no decrease in correct identities on development and test; no retuning'))
    for site in snapshot['sites']:
        events = {a['session']: a.get('moderate_additional_events', []) for a in site['clock_audit']}
        for track in site['tracks']:
            original = np.asarray(track['original_receipt_offsets_s'])
            baseline = np.asarray([p[0] for p in track['points']])
            for event in events.get(track['source_key'][0], []):
                inside = (original+snapshot['start'] >= event['receipt_start']-1e-6) & (original+snapshot['start'] <= event['receipt_end']+1e-6)
                baseline[inside] = np.round(original[inside], 2)
            # evaluate() calls its first timeline 'receipt'; here it is the
            # existing production correction, not the original raw timeline.
            track['original_receipt_offsets_s'] = baseline.tolist()
            if site['id'] not in approved:
                for point, t in zip(track['points'], baseline):
                    point[0] = float(t)
    result = {}
    for name, part in [('development', subset(snapshot, 0, 1770)),
                       ('test', subset(snapshot, 1830, 3600, earlier_ids(snapshot, 1800)))]:
        totals = evaluate(part, params)
        by_site = {site['id']: evaluate(dict(part, sites=[site]), params) for site in part['sites']}
        result[name] = dict(baseline=totals['receipt'], moderate=totals['corrected'], sites=by_site,
                            gate_pass=totals['corrected']['wrong'] <= totals['receipt']['wrong'] and totals['corrected']['correct'] >= totals['receipt']['correct'])
        atomic(folder/('matching-'+name+'.json'), result[name])
        print(name, totals, flush=True)
    result.update(enabled_sites=sorted(approved), eligible=all(result[k]['gate_pass'] for k in ('development', 'test')),
                  limitations=['Same-sensor masked-road proxy, not verified identity or synchronization between sensors.',
                               'Both methods hide identical recorded positions; selection conditional on candidate continuous tracks.',
                               'Repeated masks and missing-arrival scenarios are correlated.'])
    atomic(folder/'matching-validation.json', result)
    return result


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='data/reconstruction/moderate-delivery-validation')
    run(parser.parse_args().output)
