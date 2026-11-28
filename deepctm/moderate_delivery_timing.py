"""Experimental bounded timing repair for sub-1.5-second delivery bursts.

Keeps production corrections; only considers untouched intervals. This does not
fill absent frames, synchronize sites, or infer an SDK timezone. Explicit per-site opt-in.
"""
from collections import defaultdict, Counter
from datetime import datetime
import json
import numpy as np
from .delivery_timing import correct as baseline_correct


def correct(rows, max_span_s=60., max_delay_s=15., anchor_tolerance_s=.2,
            stable_frames=5):
    baseline, baseline_audit = baseline_correct(rows, max_span_s, max_delay_s,
                                                anchor_tolerance_s, stable_frames)
    groups = defaultdict(list)
    for row in baseline:
        groups[row[0]].append(row)
    output, audits = [], []
    for session, values in groups.items():
        received = np.asarray([v[3] for v in values])
        times = np.asarray([v[1] for v in values])
        old_times = times.copy()
        stamps = []
        for _, _, payload, _ in values:
            try:
                event = json.loads(payload)
                stamp = datetime.fromisoformat(event.get('frame', {}).get('timestamp') or event.get('timestamp'))
                stamps.append((stamp.replace(tzinfo=None)-datetime(2000, 1, 1)).total_seconds())
            except (ValueError, TypeError, KeyError):
                stamps.append(float('nan'))
        sensor = np.asarray(stamps)
        events, reasons = [], Counter()
        i = stable_frames
        while i < len(values):
            dr, ds = received[i]-received[i-1], sensor[i]-sensor[i-1]
            # Lower only the trigger. The independent anchor and clock tests
            # stay at production tolerances; no missing-frame interpolation.
            if not (.5 < dr <= 1.5 and 0 < ds <= 1.5 and dr-ds >= .25):
                i += 1
                continue
            start = i-1
            if np.any(abs(old_times[start-stable_frames+1:i+1]-received[start-stable_frames+1:i+1]) > 1e-6):
                reasons['existing_timing_correction'] += 1
                i += 1
                continue
            offset = received[start]-sensor[start]
            prior = slice(start-stable_frames+1, start+1)
            prior_steps = np.diff(sensor[prior])
            if (np.any(~np.isfinite(prior_steps)) or np.any(prior_steps <= 0)
                    or np.any(prior_steps > 1.5)
                    or np.max(abs(received[prior]-sensor[prior]-offset)) > anchor_tolerance_s):
                reasons['unstable_preceding_anchor'] += 1
                i += 1
                continue
            end = None
            reason = 'no_stable_return_anchor'
            for j in range(i, len(values)-stable_frames+1):
                if received[j]-received[start] > max_span_s:
                    break
                if abs(old_times[j]-received[j]) > 1e-6:
                    reason = 'existing_timing_correction'
                    break
                if not 0 < sensor[j]-sensor[j-1] <= 1.5:
                    reason = 'sensor_discontinuity'
                    break
                if sensor[j]-sensor[start] < 5:
                    continue
                tail = slice(j, j+stable_frames)
                increments = np.diff(sensor[j-1:j+stable_frames])
                if np.any(~np.isfinite(increments)) or np.any(increments <= 0) or np.any(increments > 1.5):
                    continue
                if np.max(abs(received[tail]-sensor[tail]-offset)) > anchor_tolerance_s:
                    continue
                rate = (received[j]-received[start])/(sensor[j]-sensor[start])
                if abs(rate-1) > .01:
                    continue
                proposed = received[start]+(sensor[start:j+1]-sensor[start])*rate
                delta = received[start:j+1]-proposed
                if np.any(delta < -.25) or np.any(delta > max_delay_s):
                    continue
                end = j
                break
            if end is None:
                reasons[reason] += 1
                i += 1
                continue
            times[start:end+1] = proposed
            events.append(dict(receipt_start=float(received[start]), receipt_end=float(received[end]),
                               frames=end-start+1, anchor_rate=float(rate),
                               sensor_elapsed_s=float(sensor[end]-sensor[start]),
                               max_receipt_delay_s=float(max(delta))))
            i = end+1
        output.extend((session, float(t), row[2], row[3]) for t, row in zip(times, values))
        audits.append(dict(session=session, events=events, rejected=dict(reasons),
                           additional_corrected_frames=int(np.sum(abs(times-old_times) > 1e-6))))
    return sorted(output, key=lambda row: row[1]), dict(baseline=baseline_audit, candidate=audits)


def correct_for_build(rows):
    """Production-compatible audit shape; caller must explicitly opt in.

    This adapter does not select sites, modify policy files or enable itself.
    The calling pipeline must apply independently reviewed per-site eligibility.
    """
    output, audits = correct(rows)
    extra = {a['session']: a for a in audits['candidate']}
    merged = []
    for baseline in audits['baseline']:
        candidate = extra[baseline['session']]
        events = [dict(event, method='bounded_delivery_v1') for event in baseline['events']]
        events += [dict(event, method='moderate_bounded_delivery_v1') for event in candidate['events']]
        merged.append(dict(baseline,
                           state='bounded_and_moderate_delivery_correction',
                           events=sorted(events, key=lambda e: e['receipt_start']),
                           corrected_frames=baseline['corrected_frames']+candidate['additional_corrected_frames'],
                           moderate_corrected_frames=candidate['additional_corrected_frames'],
                           moderate_rejected=candidate['rejected']))
    return output, merged
