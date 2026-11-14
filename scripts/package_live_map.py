"""Package tracked runtime files only; never include local data or credentials."""
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'docs/Ouster_live_map_transfer.zip'
EXACT = {
    'config/sites.json', 'config/signal_layouts.json',
    'scripts/start_connected.py', 'scripts/open_dashboard.command',
    'scripts/connect_toronto.command', 'scripts/connect_florida.command',
    'docs/Live_map_transfer_instructions.docx',
    'Data API/Realtime SDK/bctRealtimeSDK_Subscriber-3.1.0-py3-none-any.whl',
}
tracked = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
selected = sorted(p for p in tracked if p and (p.startswith('dashboard/') or p in EXACT))
assert EXACT.issubset(set(selected)), 'A required file is not tracked'
assert all(not any(part in {'.env', '.venv', '__pycache__', 'data', 'node_modules', '.git'} for part in Path(p).parts) for p in selected)
start = '''Ouster live map transfer

Read docs/Live_map_transfer_instructions.docx for the complete setup guide.
Extract this ZIP first. Run commands inside the extracted Ouster folder.
Requires Python 3.11 and internet access. macOS/Linux commands:

python3.11 -m venv .venv
.venv/bin/python -m pip install "Data API/Realtime SDK/bctRealtimeSDK_Subscriber-3.1.0-py3-none-any.whl" certifi
export SSL_CERT_FILE="$(.venv/bin/python -c 'import certifi; print(certifi.where())')"
.venv/bin/python scripts/start_connected.py --port 8766 --toronto

Enter credentials privately when prompted. Open http://127.0.0.1:8766/
Keep Terminal open. Select Approximate live objects and Per-intersection settings.
Do not start another dashboard on port 8766. Windows needs a Linux environment
such as WSL; the launcher is not a native Windows application.

Includes current per-site coordinates/rotations, the bundled Leaflet library,
SDK wheel and setup instructions. No historical data, credentials, local overrides,
virtual environment or installed dependencies are included. The application creates
data/ on first run. API sensor authorization is still required.
Use of the supplied SDK remains subject to the vendor's terms.
'''
manifest = {'git_commit': subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip(),
            'files': {p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in selected}}
with zipfile.ZipFile(OUTPUT,'w',zipfile.ZIP_DEFLATED) as archive:
    for p in selected:archive.write(ROOT/p,'Ouster/'+p)
    archive.writestr('Ouster/START_HERE.txt',start)
    archive.writestr('Ouster/TRANSFER_MANIFEST.json',json.dumps(manifest,indent=2)+'\n')
with zipfile.ZipFile(OUTPUT) as archive:
    assert archive.testzip() is None
    for p,digest in manifest['files'].items():
        assert hashlib.sha256(archive.read('Ouster/'+p)).hexdigest()==digest
print(f'{OUTPUT}\n{len(selected)+2} files; {OUTPUT.stat().st_size:,} bytes; integrity verified')
