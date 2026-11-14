"""Arm two Florida recordings from one hidden local login."""
import argparse
from datetime import date, datetime, time as wall_time
import json
import os
import subprocess
import time
from zoneinfo import ZoneInfo

import requests
from .capture import atomic
from .florida_capture import BASE, capture_window, private_credentials

EASTERN = ZoneInfo('America/New_York')
AUTH = 'https://core.api.bluecity.ai/api/token/'  # BlueCity SDK default


def windows(day):
    return [(datetime.combine(day, wall_time(a), EASTERN).timestamp(),
             datetime.combine(day, wall_time(b), EASTERN).timestamp())
            for a, b in [(7, 9), (16, 18)]]


def run(day):
    slots = [w for w in windows(day) if w[1] > time.time()]
    if not slots:
        raise SystemExit('Both selected recording windows have passed.')
    BASE.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = BASE / f'peak-{day}.json'
    status = {'state': 'awaiting_private_login', 'windows': slots, 'results': []}
    atomic(path, status)
    credentials = None
    for _ in range(3):
        username, password = private_credentials()
        try:
            with requests.post(AUTH, json={'username': username, 'password': password},
                               timeout=20, allow_redirects=False) as response:
                accepted = response.status_code == 200 and bool(response.json().get('access'))
                code = f'HTTP {response.status_code}'
        except (requests.RequestException, ValueError, AttributeError):
            accepted, code = False, 'network or invalid response'
        if accepted:
            credentials = json.dumps([username, password]) + '\n'
        del username, password
        if accepted:
            break
        status.update(state='login_failed', reason=code)
        atomic(path, status)
        print(f'BlueCity login failed ({code}). Try your BlueCity API credentials again.', flush=True)
    if credentials is None:
        raise SystemExit('No recording is armed. Relaunch with valid BlueCity API credentials.')
    awake = subprocess.Popen(['caffeinate', '-is', '-w', str(os.getpid())])
    try:
        status.pop('reason', None)
        status.update(state='armed', pid=os.getpid())
        atomic(path, status)
        print('Login accepted. Both remaining windows are armed. Keep this Terminal open, Mac plugged in, lid open, and internet connected.', flush=True)
        for start, end in slots:
            while time.time() < start - 60:
                time.sleep(min(30, max(0, start - 60 - time.time())))
            if time.time() >= end:
                result = 'missed'
            else:
                try:
                    result = capture_window(credentials, start, end)
                except Exception:
                    result = 'capture_or_processing_error'
            status['results'].append({'start': start, 'end': end, 'state': result})
            atomic(path, status)
        status['state'] = 'finished'
    except KeyboardInterrupt:
        status['state'] = 'interrupted'
    finally:
        del credentials
        awake.terminate()
        atomic(path, status)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--date', type=date.fromisoformat, required=True)
    run(parser.parse_args().date)
