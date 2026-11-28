"""Conservative timing analysis of a saved phase-only capture (no movement join)."""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import statistics

STATUS = {0: 'INVALID', 1: 'GREEN', 2: 'YELLOW', 3: 'RED'}

def analyze(folder):
    rows = [json.loads(line) for line in (folder/'raw.jsonl').read_text().splitlines()]
    states = {}; starts = {}; green = {}; episodes = []; cycles = []; vectors = []
    gaps = []; absolute_count = 0; regressions = 0; changes = []
    previous = None
    for row in rows:
        receipt = row['received_at']; event = row['event']; change = event['phaseChange']
        gap = receipt-previous if previous is not None else 0
        previous = receipt
        if gap > 60:
            gaps.append(dict(seconds=gap, before_receipt=receipt-gap, after_receipt=receipt))
            states.clear(); starts.clear(); green.clear()
        if change.get('absolute'):
            absolute_count += 1
            states.clear(); starts.clear(); green.clear()
            for p in change.get('phases', []): states[str(p['phaseNumber'])] = p.get('status', 0)
            continue
        for p in change.get('phases', []):
            n = str(p['phaseNumber']); code = p.get('status', 0)
            sensor_text = p.get('timestamp') or event.get('timestamp')
            try: sensor = datetime.fromisoformat(sensor_text)
            except (ValueError, TypeError):
                starts.pop(n, None); green.pop(n, None); states[n] = code; continue
            old = states.get(n)
            if n in starts:
                try: dt = (sensor-starts[n]['sensor']).total_seconds()
                except TypeError: dt = -1
                if dt < 0:
                    regressions += 1; starts.pop(n, None); green.pop(n, None); states.pop(n, None); continue
            if code == old: continue
            if n in starts and old in (1, 2, 3):
                start = starts[n]
                episodes.append(dict(phase=n, colour=STATUS[old], sensor_seconds=dt,
                                     receipt_seconds=receipt-start['receipt'],
                                     start_sensor=start['sensor'].isoformat(), end_sensor=sensor_text))
            if code in (1, 2, 3):
                starts[n] = dict(sensor=sensor, receipt=receipt)
            else:
                starts.pop(n, None); green.pop(n, None)
            if code == 1 and old in (2, 3):
                if n in green:
                    cycles.append(dict(phase=n, seconds=(sensor-green[n]).total_seconds()))
                green[n] = sensor
            states[n] = code
            changes.append(dict(phase=n, state=STATUS.get(code,'UNKNOWN'), sensor_time=sensor_text,
                                received_at=receipt))
        vectors.append({n:c for n,c in states.items() if c in (1,2,3)})
    phases = sorted({x['phase'] for x in episodes}, key=int)
    summary = {}
    for n in phases:
        summary[n] = {}
        for label in ['GREEN','YELLOW','RED','CYCLE']:
            values = ([x['seconds'] for x in cycles if x['phase']==n] if label=='CYCLE' else
                      [x['sensor_seconds'] for x in episodes if x['phase']==n and x['colour']==label])
            summary[n][label] = (dict(count=len(values), median=statistics.median(values),
                                      minimum=min(values),maximum=max(values)) if values else None)
    pairs = []
    for i,n in enumerate(phases):
        for m in phases[i+1:]:
            shared = [(v[n],v[m]) for v in vectors if n in v and m in v]
            if len(shared)>=10 and len({a for a,b in shared})>=2 and all(a==b for a,b in shared):
                pairs.append([n,m])
    result = dict(messages=len(rows),absolute_messages=absolute_count,
                  first_receipt=rows[0]['received_at'],last_receipt=rows[-1]['received_at'],
                  conservative_gap_cutoff_seconds=60, gaps=gaps, timestamp_regressions=regressions,
                  summary=summary, identical_observed_pairs=pairs, episodes=episodes,
                  cycles=cycles, changes=changes, movement_mapping_verified=False)
    (folder/'timing-analysis.json').write_text(json.dumps(result,indent=2))
    lines = ['# Driftwood: observed signal timing', '',
      'Receipt interval: '+ ' to '.join(datetime.fromtimestamp(result[k],timezone.utc).isoformat() for k in ['first_receipt','last_receipt'])+'.',
      f"Saved {len(rows)} messages, including {absolute_count} absolute snapshots.", '',
      '## Interpretation and limits', '',
      'Durations below use differences between sensor timestamps; their timezone is unverified. Receipt times are UTC. They are observed report intervals, not independently verified controller settings.',
      'Absolute snapshots initialize state but do not count as new transitions. The initial burst covers older sensor time. Initial/final episodes, episodes crossing any absolute snapshot, and episodes crossing receipt gaps longer than 60 seconds are excluded. This cutoff is conservative, not proof of an outage. Shorter missing-message gaps remain undetectable without transport telemetry.',
      f"Receipt gaps above 60 seconds: {len(gaps)}. Regressing transition timestamps: {regressions}.",
      'No total green/red percentages are claimed because complete delivery cannot be established.', '',
      '## Complete observed episodes', '',
      'Cells show median seconds [minimum–maximum; sample count]. Cycle means successive observed green onsets, not a verified controller cycle.', '',
      '| Live phase number | Green | Yellow | Red | Green-to-green interval |','|---|---|---|---|---|']
    for n,stats in summary.items():
        cells = [f"{v['median']:.1f} [{v['minimum']:.1f}–{v['maximum']:.1f}; n={v['count']}]" if v else 'Unavailable' for v in stats.values()]
        lines.append('| '+n+' | '+' | '.join(cells)+' |')
    lines += ['', 'Identical states at jointly observed reconstructed snapshots: '+', '.join('/'.join(p) for p in pairs)+'.',
      'These associations describe this recording only; they do not establish physical-head counts or movement mappings.', '',
      '## Comparison with Phase Details', '',
      'The October 2 Driftwood configuration has numeric labels 1, 2, 4, 5, 6, 8, 10, 11, 12, 14. Live data also contains valid 9 and 13. Configuration phase_id values are distinct database IDs. A label matching a live number is only a candidate join.',
      'If labels match live numbers, labels 2/6 would represent opposing west/east approaches, and labels 4/8 opposing south/north approaches. Their paired states are consistent with this hypothesis, but do not verify it. Configuration labels 9 and 13 are absent; nested trafficLightStatus semantics remain undocumented.',
      'No current physical head can be assigned a directional colour from this analysis alone. One intersection cannot establish corridor offsets or coordination.', '',
      '## Example received changes', '',
      'Times below are unconverted sensor timestamps. These are individual reports, not full intersection snapshots.', '',
      '| Sensor timestamp | Live phase | Reported colour |','|---|---|---|']
    for x in changes[:40]: lines.append(f"| {x['sensor_time']} | {x['phase']} | {x['state']} |")
    (folder/'timing-report.md').write_text('\n'.join(lines)+'\n')
    return result

if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('folder',type=Path);args=parser.parse_args()
    result=analyze(args.folder)
    print(json.dumps({k:v for k,v in result.items() if k not in ['changes','episodes','cycles']},indent=2))
