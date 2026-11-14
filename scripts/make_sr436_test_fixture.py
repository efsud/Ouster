import argparse
import gzip,json
from pathlib import Path
parser=argparse.ArgumentParser(description='Create a synthetic Florida browser test fixture only.')
parser.add_argument('output',type=Path)
p=parser.parse_args().output
p.mkdir()  # Refuse an existing directory, including any real archive.

c='20261113T030833Z-aaaaaa'; d=p/c; (d/'observed').mkdir(parents=True,exist_ok=True)
(p/'latest.json').write_text(json.dumps(dict(capture_id=c)))
config=json.loads(Path('config/sr436.json').read_text())
config['sites']=config['sites'][:2]
start=1794538800
for i,s in enumerate(config['sites']):
 s.update(frames=3, first_receipt=start+1200,last_receipt=start+1201, receipt_span_s=1,
          sessions=1,gaps_over_3s=2,longest_gap_s=2399,gaps=[],diagnostics={},
          archive_issues={},object_classes={str(2+i*2):3},calibrated_projection=bool(i))
 code=s['id'];m=s['station_m']
 with gzip.open(d/'observed'/(code+'.json.gz'),'wt') as out:
  json.dump([[str(2+i*2),'eastbound' if i else 'unknown',
             [[1200,m,1200.5,m+5*i,36],[1200.5,m+5*i,1201,m+10*i,36]]]],out)
(d/'config.json').write_text(json.dumps(config))
(d/'manifest.json').write_text(json.dumps(dict(state='synthetic_fixture',start=start,end=start+3600,sites=[s['id'] for s in config['sites']])))
(d/'observed/index.json').write_text(json.dumps(dict(start=start,end=start+3600,capture_id=c,sites=config['sites'],classes={'2':'Car','4':'Truck'},vehicles=['2','4'])))
