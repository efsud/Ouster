"""Read-only external-recording check of the frozen reconstruction candidates."""
import argparse,hashlib,json,tempfile,time
from pathlib import Path
from .florida_rolling import connect,build
from .figures import recorded_events
from .archive_extension import cases
from .corridor_campaign import atomic,evaluate

def load_snapshot(capture):
    from dashboard.server import sites
    root=Path(__file__).resolve().parents[1];capture=Path(capture)
    manifest=json.loads((capture/'manifest.json').read_text());entries=[s for s in sites() if s['region']=='Toronto']
    issues=[];counts={}
    # Temporary copy is isolated from both the original archive and live buffers.
    with tempfile.TemporaryDirectory(prefix='ouster-archive-review-') as tmp:
        db=connect(Path(tmp)/'frames.sqlite3')
        for site in entries:
            batch=[];count=0
            for row in recorded_events(capture,site['id'],issues):
                payload=row['payload']
                if not payload.get('frame') or not manifest['start']<=row['received_at']<=manifest['end']:continue
                encoded=json.dumps(payload,separators=(',',':'));key=hashlib.sha256((str(row['received_at'])+encoded).encode()).hexdigest()
                batch.append((site['id'],row['session'],key,row['received_at'],encoded));count+=1
                if len(batch)>=1000:db.executemany('insert or ignore into frames values(?,?,?,?,?)',batch);db.commit();batch=[]
            db.executemany('insert or ignore into frames values(?,?,?,?,?)',batch);db.commit();counts[site['id']]=count
            print('archive loaded',site['name'],count,flush=True)
        axes=json.loads((root/'config/reconstruction/corridor-road-axes.json').read_text())
        snapshot=build(db,entries,manifest['end'],road_axes=axes,processing_interval_s=.5);db.close()
    return snapshot,manifest,counts,issues

def run(capture,output,deadline):
    from .validate_shape_association import score
    from .kinematic_gate import path
    from .validate_rts_prior import prospective
    from .validate_quadratic_solver import evaluate as quadratic
    root=Path(__file__).resolve().parents[1];capture=Path(capture);output=Path(output)
    model=json.loads((root/'data/reconstruction/eight-hour-20261123/finch/model.json').read_text())
    snapshot,manifest,counts,issues=load_snapshot(capture)
    result={'state':'evaluating','capture':str(capture),'window':[manifest['start'],manifest['end']],
        'manifest_sha256':hashlib.sha256((capture/'manifest.json').read_bytes()).hexdigest(),
        'received_frame_counts':counts,'read_issues':issues,'transform_manifest':snapshot['transform_manifest'],
        'parameters':model['parameters'],'car_fragments':sum(t['class_type']=='2' for s in snapshot['sites'] for t in s['tracks']),
        'limitations':['An older daytime recording, not a future prospective window.',
        'Current provisional geometry is used for both visible inputs and masked truth; not an alignment validation.',
        'Parameters stay frozen; no fitting on this capture.',
        'Same-sensor masks cannot establish actual cross-sensor identities.','Repeated widths and gaps reuse vehicles.']}
    atomic(output,result)
    result['local']=evaluate(cases(snapshot,'test',10),model['parameters'],deadline);atomic(output,result)
    report={'selected_method':'kinematic_0.01','calibration':{'parameters':model['parameters']}}
    result['association']=score(snapshot,report,['current',.5],limit=40,deadline=deadline,path_gate=path);atomic(output,result)
    protocol=json.loads((root/'data/reconstruction/rts-review/protocol.json').read_text())
    result['rts']=prospective(snapshot,model['parameters'],protocol,deadline);atomic(output,result)
    result['quadratic']=quadratic(snapshot,model['parameters'],deadline)
    result['state']='complete' if time.time()<deadline else 'deadline_reached';atomic(output,result)
    print('archive evaluation',result['state'],result['association']['totals'],flush=True)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--capture',required=True);p.add_argument('--output',required=True);p.add_argument('--deadline',type=float,required=True)
    a=p.parse_args();run(a.capture,a.output,a.deadline)
