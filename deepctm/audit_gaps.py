"""Explain same-ID fragment boundaries without treating every endpoint as missing data."""
import argparse,json
from collections import Counter,defaultdict
from datetime import datetime
from pathlib import Path
from .spatial_bridges import endpoint

def audit(snapshot):
    result=[]
    for site in snapshot['sites']:
        groups=defaultdict(list);counts=Counter()
        for track in site['tracks']:
            key=track.get('source_key',[])
            if len(key)==3:groups[tuple(key[:2])].append(track)
        for tracks in groups.values():
            tracks.sort(key=lambda t:t['points'][0][0])
            for a,b in zip(tracks,tracks[1:]):
                dt=b['points'][0][0]-a['points'][-1][0]
                if not 1.5<dt<=120:continue
                counts['same_id_pairs_1_5_to_120s']+=1
                if a['direction']!=b['direction']:counts['direction_change']+=1;continue
                ea,eb=endpoint(a['points'],True),endpoint(b['points'],False)
                if not ea or not eb:counts['short_endpoint_context']+=1;continue
                if abs(a['lateral_end_m']-b['lateral_start_m'])>2:counts['lateral_displacement']+=1;continue
                try:ratio=(datetime.fromisoformat(b['sensor_start'])-datetime.fromisoformat(a['sensor_end'])).total_seconds()/dt
                except (KeyError,ValueError,TypeError):counts['clock_unavailable']+=1;continue
                if not .8<=ratio<=1.2:counts['clock_disagreement']+=1;continue
                counts['passes_initial_geometry_time']+=1
                if dt>30:counts['longer_than_30s_requires_outage']+=1
                if a['class_type']!=b['class_type']:counts['class_change']+=1
        result.append({'site':site['id'],'name':site['name'],'counts':dict(counts)})
    return {'geometry_version':snapshot.get('geometry_version','inter-sensor-chord-v1'),'window':[snapshot['start'],snapshot['end']],'sites':result,
            'limitations':['Counts describe fragment boundaries, not ground-truth missing vehicles.','Passing these checks does not guarantee physical reconstruction or identity correctness.','Turn exits and field-of-view endpoints need not connect.']}
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--snapshot',required=True);parser.add_argument('--output',required=True);args=parser.parse_args()
    Path(args.output).write_text(json.dumps(audit(json.loads(Path(args.snapshot).read_text())),indent=2))
