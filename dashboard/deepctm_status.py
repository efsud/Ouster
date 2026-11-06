"""Read-only DeepCTM experiment status; does not import the ML runtime or open raw DBs."""
import json
from pathlib import Path
import time
import sqlite3

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
        if site in manifest.get('unavailable_sites',[]):value.update(state='unavailable after retries',receiving_now=False)
        health_path=directory/(site+'-health.sqlite3')
        if health_path.exists() and not value['receiving_now']:
            try:
                db=sqlite3.connect('file:'+str(health_path)+'?mode=ro',uri=True)
                try:
                    row=db.execute('SELECT payload FROM collector_health WHERE site=?',(site,)).fetchone()
                    health=json.loads(row[0]) if row else {}
                    if health.get('error'):value['error']=health['error']
                finally:db.close()
            except (sqlite3.Error,ValueError):pass
        sensors.append(value)
    config=json.loads((directory/'config.json').read_text())
    name_map=dict(zip(config['sites_west_to_east'],config['site_names']))
    for sensor in sensors:sensor['name']=name_map.get(sensor['site'],sensor['site'])
    report_path=directory/'report.json'
    return {'capture_id':directory.name,'title':config.get('title','Weston ↔ Signet / Arrow'),'figures_state':manifest.get('figures_state'),'state':manifest['state'],'start':manifest['start'],'end':manifest['end'],'error':manifest.get('error'),'sensors':sensors,'report':json.loads(report_path.read_text()) if report_path.exists() else None,'assumptions':json.loads((directory/'config.json').read_text())['assumptions']}


def figure_asset(name, root=ROOT):
    """Serve only generated, indexed figures from the current capture."""
    base=Path(root)/'data/deepctm'
    directory=Path(json.loads((base/'latest.json').read_text())['directory']).resolve()
    if not directory.is_relative_to(base.resolve()):raise ValueError('Invalid experiment directory')
    folder=directory/'figures';index=folder/'index.json'
    if name=='index.json':return index.read_bytes(),'application/json'
    allowed={entry['file'] for entry in json.loads(index.read_text())['figures']}
    if name not in allowed or Path(name).name!=name:raise ValueError('Unknown figure')
    path=(folder/name).resolve()
    if not path.is_relative_to(folder.resolve()):raise ValueError('Invalid figure path')
    return path.read_bytes(),'image/png'
