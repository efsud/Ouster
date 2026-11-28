"""Private, read-only 30-minute phase capture and receipt-time decoding."""
import getpass
import json
import os
from pathlib import Path
import queue
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
STATUS = {0: 'INVALID', 1: 'GREEN', 2: 'YELLOW', 3: 'RED'}


def decode(event):
    change = event.get('phaseChange', {})
    return [dict(phase=str(p.get('phaseNumber', 'unknown')),
                 state=STATUS.get(p.get('status', 0), 'UNKNOWN'),
                 sensor_timestamp=p.get('timestamp') or event.get('timestamp'))
            for p in change.get('phases', [])]


def main():
    import certifi
    os.environ['SSL_CERT_FILE'] = certifi.where()
    from realtime_subscriber.Realtime_subscriber_api import BCTWSConnection
    from google.protobuf.json_format import MessageToDict
    site = 'OBC-AG-SA-C618861'
    print('Finch W & Driftwood: read-only phase capture for 30 minutes after first receipt.')
    username = input('BlueCity username: ').strip()
    password = getpass.getpass('BlueCity password (hidden): ')
    folder = ROOT / 'data' / 'signal-samples' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    folder.mkdir(parents=True)
    stream = None
    rows = []
    first = None
    initialized = False
    outcome = 'interrupted'
    started = time.monotonic()
    try:
        stream = BCTWSConnection(UDID=site, username=username, password=password,
            singleton=True, subscriptions=[BCTWSConnection.subscriptionOption.PHASE_CHANGE],
            semantic_abs=False)
        password = None
        with (folder / 'raw.jsonl').open('a') as raw:
            while first is None or time.monotonic() - first < 1800:
                try:
                    message = stream.queue.get(timeout=1)
                except queue.Empty:
                    if first is None and time.monotonic() - started > 90:
                        outcome = 'no_initial_data'; break
                    if not stream.p.is_alive():
                        outcome = 'sdk_stopped'; break
                    continue
                event = MessageToDict(message)
                if 'phaseChange' not in event:
                    continue
                receipt = time.time()
                if first is None:
                    first = time.monotonic()
                    print('First phase message received. Recording for 30 minutes. Keep this window open.', flush=True)
                record = dict(site=site, received_at=receipt, event=event)
                raw.write(json.dumps(record) + '\n'); raw.flush(); os.fsync(raw.fileno())
                absolute = event['phaseChange'].get('absolute', False)
                initialized = initialized or absolute
                rows.append(dict(received_at=receipt, absolute=absolute, phases=decode(event)))
            else:
                outcome = 'capture_window_elapsed'
    except KeyboardInterrupt:
        outcome = 'interrupted'
    except Exception as exc:
        outcome = 'error_' + type(exc).__name__
    finally:
        if stream is not None and stream.p.is_alive():
            stream.p.terminate(); stream.p.join(timeout=5)
        report = dict(site=site, outcome=outcome, requested_seconds=1800,
                      capture_elapsed_seconds=time.monotonic()-first if first else 0,
                      messages=len(rows), absolute_received=initialized,
                      movement_mapping_verified=False, timeline=rows,
                      limitations=['Receipt time is UTC; sensor timestamp timezone is unverified.',
                                   'Phase labels are not verified joins to realtime phase numbers.',
                                   'Silence on a change-only stream cannot establish connection health.',
                                   'No physical-head or corridor-coordination claims.'])
        (folder / 'decoded.json').write_text(json.dumps(report, indent=2))
        lines = ['# Driftwood signal sample', '', f'Outcome: {outcome}; messages: {len(rows)}.',
                 '', 'Times below are computer receipt times in UTC, not verified sensor event times.',
                 'Directions remain unverified. Repeated reports are preserved, not treated as new transitions.',
                 '', '| Receipt time (UTC) | Absolute snapshot | Phase | Reported colour | Sensor timestamp |',
                 '|---|---|---|---|---|']
        for row in rows:
            for phase in row['phases']:
                if phase['state'] == 'INVALID': continue
                lines.append(f"| {datetime.fromtimestamp(row['received_at'], timezone.utc).isoformat()} | {row['absolute']} | {phase['phase']} | {phase['state']} | {phase['sensor_timestamp']} |")
        (folder / 'report.md').write_text('\n'.join(lines)+'\n')
        print(f'Capture {outcome}. Saved raw.jsonl, decoded.json and report.md in {folder}', flush=True)


if __name__ == '__main__':
    main()
