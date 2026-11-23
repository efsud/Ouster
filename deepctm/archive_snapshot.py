"""Read preserved Florida archives without changing live buffers or raw data."""
import argparse,gzip,json,sqlite3
from pathlib import Path
from .florida_rolling import connect,build

def run(capture,output):
    from dashboard.server import sites
    capture=Path(capture);output=Path(output);output.mkdir(parents=True,exist_ok=True)
    manifest=json.loads((capture/'manifest.json').read_text());start=manifest['start'];end=start+3600
    db=connect(':memory:');audit={}
    for path in sorted(capture.glob('*.jsonl.gz')):
        scanned=kept=0;last=-1e30
        with gzip.open(path,'rt') as stream:
            for line in stream:
                row=json.loads(line);t=row['received_at']
                if t>end:break
                scanned+=1
                if t<start or t-last<.49 or not row['payload'].get('frame'):continue
                last=t;kept+=1
                db.execute('INSERT OR IGNORE INTO frames VALUES(?,?,?,?,?)',(row['site'],row['session'],str(t),t,json.dumps(row['payload'])))
        audit[path.name]={'scanned_records':scanned,'sampled_frames':kept,'bytes':path.stat().st_size}
        print(path.name,scanned,kept,flush=True)
    db.commit();snapshot=build(db,[s for s in sites() if s['region']=='Florida'],end);db.close()
    snapshot['archive_provenance']={'capture':str(capture),'audit':audit,'window_seconds':3600,'phase_state':'Not imported: archived raw phase changes require independently validated state replay','alignment':'Current provisional site calibration applied retrospectively'}
    (output/'snapshot.json').write_text(json.dumps(snapshot,separators=(',',':')))
    print('Saved',output,[(s['name'],len(s['tracks'])) for s in snapshot['sites']],flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--capture',required=True);p.add_argument('--output',required=True);a=p.parse_args();run(a.capture,a.output)
