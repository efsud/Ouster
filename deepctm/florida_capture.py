"""Private-terminal, isolated SR-436 capture; credentials transferred over pipes."""
import argparse
import base64
import getpass
import gzip
import json
import os
from pathlib import Path
import queue
import shutil
import signal
import sqlite3
import subprocess
import sys
import time
import uuid

from .capture import atomic, stop

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'data/sr436'
CONFIG = ROOT / 'config/sr436.json'
GAP_S = 3.0
MIN_FREE = 2 * 1024**3
FAILURE_CODES = {'auth_http_400', 'auth_http_401', 'auth_http_403',
                 'beacon_http_403', 'beacon_http_404', 'grpc_permission_denied'}


def health_code(directory, site):
    try:
        path = directory / (site + '-health.sqlite3')
        db = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=.1)
        try:
            row = db.execute('SELECT payload FROM collector_health WHERE site=?', (site,)).fetchone()
            code = json.loads(row[0]).get('error') if row else None
            if isinstance(code, str) and code.startswith(('auth_', 'beacon_', 'grpc_', 'sdk_')):
                return code
        finally:
            db.close()
    except (sqlite3.Error, ValueError, TypeError):
        pass
    return None


def worker(site, directory, start, end):
    from dashboard.sdk_client import ObservableConnection
    from dashboard.storage import Store
    from google.protobuf.json_format import MessageToDict
    username, password = json.loads(sys.stdin.readline())
    session = uuid.uuid4().hex
    path = directory / (site + '-status.json')
    state = dict(site=site, session=session, state='connecting', frames=0,
                 preflight_frames=0, events=0, last_frame=None)
    stream = None
    atomic(path, state)
    try:
        health = directory / (site + '-health.sqlite3')
        Store(health)
        options = ObservableConnection.subscriptionOption
        stream = ObservableConnection(UDID=site, username=username, password=password,
            singleton=True, store_path=str(health), site_id=site,
            subscriptions=[options.FRAME, options.PHASE_CHANGE, options.LOOP_CHANGE],
            semantic_abs=False)
        output_path = directory / f'{site}-{session}.jsonl.gz'
        last_status = time.monotonic()
        with gzip.open(output_path, 'xt', encoding='utf-8', compresslevel=3) as output:
            while time.time() < end:
                if time.monotonic() - last_status >= 1:
                    output.flush()
                    if shutil.disk_usage(directory).free < MIN_FREE:
                        raise RuntimeError('insufficient_disk')
                    atomic(path, state)
                    last_status = time.monotonic()
                try:
                    message = stream.queue.get(timeout=.25)
                except queue.Empty:
                    if not stream.p.is_alive():
                        raise RuntimeError('sdk_worker_stopped')
                    continue
                receipt = time.time()
                if receipt >= end:
                    break
                frame = message.HasField('frame')
                if frame:
                    state.update(state='receiving', last_frame=receipt)
                if receipt < start:
                    state['preflight_frames'] += int(frame)
                    continue
                payload = MessageToDict(message)
                # Preserve the decoded SDK message and its serialized protobuf.
                # Neither representation contains authentication material.
                row = dict(site=site, session=session, received_at=receipt, payload=payload,
                           protobuf_b64=base64.b64encode(message.SerializeToString()).decode('ascii'))
                output.write(json.dumps(row, separators=(',', ':')) + '\n')
                state['events'] += 1
                state['frames'] += int(frame)
        state['state'] = 'complete'
    except KeyboardInterrupt:
        state['state'] = 'interrupted'
    except Exception:
        state.update(state='failed', error=health_code(directory, site) or 'sdk_or_storage_error')
    finally:
        if stream is not None and stream.p.is_alive():
            stream.p.terminate()
            stream.p.join(timeout=5)
        atomic(path, state)


def private_credentials():
    if not sys.stdin.isatty() or not sys.stderr.isatty():
        raise SystemExit('Open the private Terminal launcher to enter credentials.')
    # Hide both fields, including the username, from Terminal scrollback.
    username = getpass.getpass('BlueCity API username (hidden): ').strip()
    password = getpass.getpass('BlueCity API password (hidden): ')
    if not username or not password:
        raise SystemExit('Both credentials are required.')
    return username, password


def capture(seconds=3600):
    credential_message = json.dumps(private_credentials()) + '\n'
    start = time.time() + 60
    return capture_window(credential_message, start, start + seconds)


def capture_window(credential_message, start, end):
    config = json.loads(CONFIG.read_text())
    now = time.time()
    seconds = end - start
    directory = BASE / (time.strftime('%Y%m%dT%H%M%SZ', time.gmtime(now)) + '-' + uuid.uuid4().hex[:6])
    directory.mkdir(mode=0o700, parents=True)
    atomic(directory / 'config.json', config)
    sites = [site['id'] for site in config['sites']]
    manifest = dict(state='checking_reception', start=start, end=end, sites=sites,
                    restarts={}, unavailable={}, format='gzip JSONL with serialized SDK protobuf')
    atomic(directory / 'manifest.json', manifest)
    atomic(BASE / 'latest.json', {'capture_id': directory.name})
    print(f'Checking seven sensors for actual FRAME reception; {seconds/3600:g}-hour window begins in {max(0, round(start-now))} seconds.', flush=True)
    children, launched, verified = {}, {}, set()
    awake = None

    def launch(site):
        child = subprocess.Popen(
            [sys.executable, '-m', __name__ if __name__ != '__main__' else 'deepctm.florida_capture',
             '--worker', site, '--directory', str(directory), '--start', str(start), '--end', str(end)],
            cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            text=True, start_new_session=True)
        children[site] = child
        launched[site] = time.time()
        try:
            child.stdin.write(credential_message)
            child.stdin.close()
        except BrokenPipeError:
            pass

    try:
        if sys.platform == 'darwin':
            awake = subprocess.Popen(['caffeinate', '-i', '-w', str(os.getpid())])
        for site in sites:
            launch(site)
        while time.time() < end:
            t = time.time()
            if t >= start and manifest['state'] == 'checking_reception':
                manifest['state'] = 'recording'
                print(f'Recording the fixed {seconds/3600:g}-hour window. Keep this Terminal open.', flush=True)
            if shutil.disk_usage(directory).free < MIN_FREE:
                manifest['state'] = 'disk_limit'
                break
            for site in sites:
                if site in manifest['unavailable']:
                    continue
                status = directory / (site + '-status.json')
                state = json.loads(status.read_text()) if status.exists() else {}
                last = state.get('last_frame') or 0
                if last >= launched[site] and site not in verified:
                    verified.add(site)
                    print(f'{site}: FRAME reception verified.', flush=True)
                if t - max(last, launched[site]) < 60 and children[site].poll() is None:
                    continue
                if t - launched[site] < 10:
                    continue
                code = health_code(directory, site) or 'no_recent_frames'
                stop(children[site])
                count = manifest['restarts'].get(site, 0)
                if code in FAILURE_CODES or count >= 3:
                    manifest['unavailable'][site] = code
                    print(f'{site}: unavailable ({code}). Other sensors continue.', flush=True)
                else:
                    manifest['restarts'][site] = count + 1
                    launch(site)
            manifest['verified_reception'] = sorted(verified)
            atomic(directory / 'manifest.json', manifest)
            if not verified and len(manifest['unavailable']) == len(sites):
                manifest['state'] = 'no_reception'
                break
            time.sleep(2)
        else:
            manifest['state'] = 'captured'
    except KeyboardInterrupt:
        manifest['state'] = 'interrupted'
    except Exception:
        manifest['state'] = 'capture_error'
    finally:
        if manifest['state'] == 'captured':
            # Let workers close gzip members naturally at the deadline.
            for child in children.values():
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    stop(child)
        else:
            for child in children.values():
                stop(child)
        if awake:
            awake.terminate()
        manifest['finished_at'] = time.time()
        atomic(directory / 'manifest.json', manifest)
    print(f"Capture {manifest['state']}: {directory}", flush=True)
    # Reports and viewer generation never use credentials.
    del credential_message
    from .florida_tracks import generate
    generate(directory)
    return manifest['state']


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--seconds', type=int, choices=(3600, 7200), default=3600,
                   help='Length of the capture after the 60-second reception check')
    p.add_argument('--worker')
    p.add_argument('--directory', type=Path)
    p.add_argument('--start', type=float)
    p.add_argument('--end', type=float)
    a = p.parse_args()
    if a.worker:
        worker(a.worker, a.directory, a.start, a.end)
    else:
        capture(a.seconds)


if __name__ == '__main__':
    main()
