"""Prompt privately for credentials, then start the local server and SDK recorder.

Run from the repository root: .venv/bin/python scripts/start_connected.py
No credentials are written to disk, URLs, Git, or command-line arguments.
"""
import getpass
import argparse
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import socket
import json
import time
import signal

ROOT = Path(__file__).resolve().parents[1]

def restart_reason(process,health,started,now):
    if process.poll() is not None:return 'collector_exited'
    if now-started<60:return None
    if health.get('state') in {'authentication_failed','routing_failed'}:return None
    last=health.get('last_receipt')
    if now-max(started,last or started)>30:return 'receipt_timeout'
    return None

def stop_group(child):
    try:os.killpg(child.pid,signal.SIGINT)
    except ProcessLookupError:return
    try:child.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:os.killpg(child.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        child.wait()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--duration',type=int,default=0,help='Stop collection after this many seconds; 0 runs until Ctrl+C')
    parser.add_argument('--record-duration',type=int,default=None,help='Raw history seconds; 0 live-only, omitted unlimited. Does not stop live streaming.')
    network=parser.add_mutually_exclusive_group()
    network.add_argument('--florida',action='store_true',help='Record all seven Florida UDIDs from config/sites.json')
    network.add_argument('--toronto',action='store_true',help='Record all ten Toronto UDIDs from config/sites.json')
    args=parser.parse_args()
    if args.record_duration is not None and args.record_duration<0:raise SystemExit('Record duration must be nonnegative.')
    if args.duration<0:raise SystemExit('Duration must be nonnegative.')
    if not 1<=args.port<=65535: raise SystemExit('Port must be between 1 and 65535.')
    with socket.socket() as probe:
        try: probe.bind(('127.0.0.1',args.port))
        except OSError:
            raise SystemExit(f'Port {args.port} is occupied. Stop the preview or use --port {args.port+1}.')
    if not sys.stdin.isatty():
        raise SystemExit('Run this launcher in an interactive terminal so your password stays hidden.')
    if importlib.util.find_spec('realtime_subscriber') is None:
        raise SystemExit('Install the bundled SDK first. See README.md, Connected mode.')
    sys.path.insert(0,str(ROOT))
    from dashboard.storage import Store
    store=Store(os.getenv('OUSTER_DB',str(ROOT/'data/ouster.sqlite3')))
    udids=[]
    if args.florida or args.toronto:
        region='Toronto' if args.toronto else 'Florida'
        udids=[s['id'] for s in json.loads((ROOT/'config/sites.json').read_text())['sites'] if s['region']==region]
        print(f'{region}: {len(udids)} configured sensor UDIDs selected.')
    print('BlueCity read-only access — credentials remain in process memory.')
    username = input('BlueCity API username: ').strip()
    password = getpass.getpass('BlueCity API password (hidden): ')
    if not (args.florida or args.toronto):
        udids = list(dict.fromkeys(s.strip() for s in input('Sensor UDIDs, comma separated (blank for historical only): ').split(',') if s.strip()))
    if not username or not password:
        raise SystemExit('Username and password are required.')
    env = dict(os.environ,BLUECITY_USERNAME=username,BLUECITY_PASSWORD=password)
    children = [];commands=[];started=[]
    record_until=time.time()+args.record_duration if args.record_duration is not None else None
    try:
        children.append(subprocess.Popen([sys.executable,'-m','dashboard.server','--port',str(args.port)],cwd=ROOT,env=env,start_new_session=True))
        for udid in udids:
            command=[sys.executable,'-m','dashboard.collector','--site',udid]
            if record_until is not None:command+=['--record-until',str(record_until)]
            commands.append(command);started.append(time.time())
            children.append(subprocess.Popen(command,cwd=ROOT,env=env,start_new_session=True))
        print(f'Open http://127.0.0.1:{args.port}. Ctrl+C stops the server and recorders.')
        print('Add verified site metadata to config/sites.local.json before mapping this stream.')
        deadline=time.monotonic()+args.duration if args.duration else None
        if deadline:print(f'Test recording automatically stops after {args.duration} seconds.',flush=True)
        while children[0].poll() is None:
            if deadline and time.monotonic()>=deadline:
                print('Test duration reached. Stopping collection; saved observations remain in SQLite.',flush=True);break
            now=time.time()
            for i,udid in enumerate(udids):
                if now-started[i]<60:continue
                reason=restart_reason(children[i+1],store.health(udid),started[i],now)
                if reason:
                    stop_group(children[i+1])
                    children[i+1]=subprocess.Popen(commands[i],cwd=ROOT,env=env,start_new_session=True)
                    started[i]=time.time()
                    print(f'{udid}: reconnecting ({reason}). Historical recording deadline unchanged.',flush=True)
            time.sleep(1)
    except KeyboardInterrupt:
        print('\nStopping read-only services.')
    finally:
        for child in children:stop_group(child)

if __name__=='__main__': main()
