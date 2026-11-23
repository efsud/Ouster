"""Compare a frozen map transform on future recorded segments; no fitting."""
import argparse,json,sqlite3,time
from pathlib import Path
from .audit_buffer_alignment import segments,plot_comparison
from .corridor_campaign import atomic
from scripts.audit_map_rotations import roads,score

def run(protocol_path,output):
    root=Path(__file__).resolve().parents[1];plan=json.loads(Path(protocol_path).read_text())
    site=next(s for s in json.loads((root/'config/sites.json').read_text())['sites'] if s['id']==plan['site'])
    region='finch' if site['region']=='Toronto' else 'florida'
    from .buffer_snapshot import copy_buffer
    db=copy_buffer(root/f'data/{region}-rolling/buffer.sqlite3')
    end=db.execute('select max(received) from frames where site=?',(site['id'],)).fetchone()[0]
    start=plan['after']+30
    result={'site':site['id'],'window':[start,end],'protocol':str(protocol_path),'created_at':time.time()}
    if end is None or end-start<300:
        result['state']='waiting_for_five_minutes_future_data';db.close();atomic(Path(output),result);return result
    p=segments(db.execute('select session,received,payload from frames where site=? and received>? order by received',(site['id'],start)));db.close()
    result['segments']=len(p)
    if len(p)<100:result['state']='insufficient_moving_segments';atomic(Path(output),result);return result
    a,b,names,oneway=roads(json.loads((root/f'data/alignment/{site["region"]}-roads.json').read_text())['elements'],site['reference_location'])
    if not len(a):result['state']='no_cached_roads';atomic(Path(output),result);return result
    for name in ('current','candidate'):
        selected=p.copy()
        if plan[name+'_mirror_y']:selected[:,[2,4]]*=-1
        result[name]=score(selected,a,b,plan[name+'_rotation_deg'],True,oneway)
    result.update(state='review_required',limitations=['No calibration applied automatically.','OSM geometry and sensor origin remain provisional.','Segments are correlated, not independent vehicles.','No cross-sensor identity or phase mapping validated.'])
    plot_comparison(p,a,b,names,(plan['current_rotation_deg'],plan['current_mirror_y'],'Current '+site['name']),
        (plan['candidate_rotation_deg'],plan['candidate_mirror_y'],'Frozen candidate on later data'),Path(output).with_suffix('.png'))
    atomic(Path(output),result);return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--protocol',required=True);p.add_argument('--output',required=True);a=p.parse_args();print(json.dumps(run(a.protocol,a.output),indent=2))
