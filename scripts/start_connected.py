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

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8765)
    network=parser.add_mutually_exclusive_group()
    network.add_argument('--florida',action='store_true',help='Record all seven Florida UDIDs from config/sites.json')
    network.add_argument('--toronto',action='store_true',help='Record all ten Toronto UDIDs from config/sites.json')
    args=parser.parse_args()
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
    Store(os.getenv('OUSTER_DB',str(ROOT/'data/ouster.sqlite3')))
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
    children = []
    try:
        children.append(subprocess.Popen([sys.executable,'-m','dashboard.server','--port',str(args.port)],cwd=ROOT,env=env))
        for udid in udids:
            children.append(subprocess.Popen([sys.executable,'-m','dashboard.collector','--site',udid],cwd=ROOT,env=env))
        print(f'Open http://127.0.0.1:{args.port}. Ctrl+C stops the server and recorders.')
        print('Add verified site metadata to config/sites.local.json before mapping this stream.')
        children[0].wait()
    except KeyboardInterrupt:
        print('\nStopping read-only services.')
    finally:
        for child in children:
            child.terminate()
        for child in children:
            try: child.wait(timeout=5)
            except subprocess.TimeoutExpired: child.kill(); child.wait()

if __name__=='__main__': main()
