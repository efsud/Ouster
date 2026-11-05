"""Read-only DeepCTM experiment status; does not import the ML runtime or open raw DBs."""
import json
from pathlib import Path
import time

ROOT=Path(__file__).resolve().parents[1]

def status(root=ROOT):
    base=Path(root)/'data/deepctm';latest=base/'latest.json'
    if not latest.exists():return {'state':'not_started','sensors':[],'report':None}
    directory=Path(json.loads(latest.read_text())['directory']).resolve()
    if not directory.is_relative_to(base.resolve()):raise ValueError('Invalid experiment directory')
    manifest=json.loads((directory/'manifest.json').read_text())
    sensors=[];now=time.time()
    for site in manifest['sites']:
        path=directory/(site+'-status.json');value=json.loads(path.read_text()) if path.exists() else {'site':site,'state':'connecting'}
        last=value.get('last_receipt');value['age_seconds']=max(0,now-last) if last else None
        value['receiving_now']=bool(last and now-last<5 and manifest['state']=='recording')
        sensors.append(value)
    report_path=directory/'report.json'
    return {'state':manifest['state'],'start':manifest['start'],'end':manifest['end'],'error':manifest.get('error'),'sensors':sensors,'report':json.loads(report_path.read_text()) if report_path.exists() else None,'assumptions':json.loads((directory/'config.json').read_text())['assumptions']}
