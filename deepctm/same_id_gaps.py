"""Class-independent same-site identity continuity, with retained evidence gates."""
from collections import defaultdict
from datetime import datetime
from .local_gaps import VEHICLES
from .spatial_bridges import endpoint


def candidates(site):
    groups=defaultdict(list)
    for tr in site['tracks']:
        key=tr.get('source_key',[])
        if len(key)==3 and tr.get('class_type') in VEHICLES:
            groups[tuple(key[:2])].append(tr)
    for identity,tracks in groups.items():
        tracks.sort(key=lambda tr:tr['points'][0][0])
        for before,after in zip(tracks,tracks[1:]):
            # Same-class gaps already have collector-chain evidence elsewhere.
            if before['class_type']==after['class_type']:continue
            if before['direction']!=after['direction']:continue
            a=endpoint(before['points'],True);b=endpoint(after['points'],False)
            if not a or not b or not .1<b['t']-a['t']<=30:continue
            try:
                ratio=(datetime.fromisoformat(after['sensor_start'])-datetime.fromisoformat(before['sensor_end'])).total_seconds()/(b['t']-a['t'])
                lateral=abs(after['lateral_start_m']-before['lateral_end_m'])
            except (KeyError,TypeError,ValueError):continue
            if not .8<=ratio<=1.2 or lateral>2:continue
            ma=before.get('movement',{}).get('movement');mb=after.get('movement',{}).get('movement')
            if ma and mb and ma!=mb:continue
            sign=1 if before['direction']=='eastbound' else -1
            if (b['x']-a['x'])*sign<0 or min(a['v']*sign,b['v']*sign)<-.25:continue
            yield dict(a=a,b=b,identity=identity,classes=[before['class_type'],after['class_type']],direction=before['direction'])
