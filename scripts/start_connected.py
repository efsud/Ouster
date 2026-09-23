"""Prompt privately for credentials, then start the local server and SDK recorder.

Run from the repository root: .venv/bin/python scripts/start_connected.py
No credentials are written to disk, URLs, Git, or command-line arguments.
"""
import getpass
import importlib.util
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

def main():
    if not sys.stdin.isatty():
        raise SystemExit('Run this launcher in an interactive terminal so your password stays hidden.')
    if importlib.util.find_spec('realtime_subscriber') is None:
        raise SystemExit('Install the bundled SDK first. See README.md, Connected mode.')
    print('BlueCity read-only access — credentials remain in process memory.')
    username = input('BlueCity API username: ').strip()
    password = getpass.getpass('BlueCity API password (hidden): ')
    udid = input('Toronto sensor UDID (blank starts historical access only): ').strip()
    if not username or not password:
        raise SystemExit('Username and password are required.')
    env = dict(os.environ,BLUECITY_USERNAME=username,BLUECITY_PASSWORD=password)
    children = []
    try:
        children.append(subprocess.Popen([sys.executable,'-m','dashboard.server'],cwd=ROOT,env=env))
        if udid:
            children.append(subprocess.Popen([sys.executable,'-m','dashboard.collector','--site',udid],cwd=ROOT,env=env))
        print('Open http://127.0.0.1:8765. Ctrl+C stops both processes.')
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
