"""Class-independent same-site identity continuity, with retained evidence gates."""
from collections import defaultdict
from datetime import datetime
from .local_gaps import VEHICLES
from .spatial_bridges import endpoint


def candidates(site,include_same_class=False,allow_lateral_motion=False,audit=None,allow_stationary_noise=False):
    groups=defaultdict(list)
    for tr in site['tracks']:
        key=tr.get('source_key',[])
        if len(key)==3:
            groups[tuple(key[:2])].append(tr)
    for identity,tracks in groups.items():
        tracks.sort(key=lambda tr:tr['points'][0][0])
        for before,after in zip(tracks,tracks[1:]):
            a=b=None
            def record(reason):
                if audit is not None:audit({'identity':identity,'start':before['points'][-1][0],'end':after['points'][0][0],'reason':reason,
                    'start_endpoint':a,'end_endpoint':b,'direction':before.get('direction'),
                    'lateral_delta_m':abs(after.get('lateral_start_m',0)-before.get('lateral_end_m',0)) if 'lateral_start_m' in after and 'lateral_end_m' in before else None})
            if before.get('class_type') not in VEHICLES or after.get('class_type') not in VEHICLES:
                record('unsupported_endpoint_class');continue
            if before['direction']!=after['direction']:
                record('endpoint_directions_disagree');continue
            a=endpoint(before['points'],True);b=endpoint(after['points'],False)
            if not a or not b:
                record('insufficient_continuous_endpoint_context');continue
            if not .1<b['t']-a['t']<=120:
                record('duration_outside_supported_range');continue
            duration=b['t']-a['t']
            # Long gaps require independent missing-frame evidence, not merely
            # disappearance of this particular ID in otherwise healthy frames.
            missing=sum(max(0,min(b['t'],hi)-max(a['t'],lo)) for lo,hi in site.get('observation_gaps',site.get('receipt_gaps',[])))
            outage=missing/duration>=.8
            if duration>30 and not outage:
                record('long_gap_without_recording_outage');continue
            same_class=before['class_type']==after['class_type']
            if same_class and not outage and (not include_same_class or duration<=1.5):
                record('same_class_recovery_disabled_or_gap_already_drawn');continue
            try:
                ratio=(datetime.fromisoformat(after['sensor_start'])-datetime.fromisoformat(before['sensor_end'])).total_seconds()/(b['t']-a['t'])
                lateral=abs(after['lateral_start_m']-before['lateral_end_m'])
            except (KeyError,TypeError,ValueError):
                record('missing_clock_or_lateral_context');continue
            if not .8<=ratio<=1.2:
                record('sensor_receipt_duration_disagreement');continue
            if lateral>(7.2 if allow_lateral_motion else 2):
                record('lateral_displacement_outside_gate');continue
            if lateral>2 and duration>30:
                record('long_lateral_gap_unsupported');continue
            ma=before.get('movement',{}).get('movement');mb=after.get('movement',{}).get('movement')
            if ma and mb and ma!=mb:
                record('movement_labels_disagree');continue
            sign=1 if before['direction']=='eastbound' else -1
            quiet=False
            if (b['x']-a['x'])*sign<0 or min(a['v']*sign,b['v']*sign)<-.25:
                from .stationary_plateau import estimate
                quiet=allow_stationary_noise and estimate(a,b,same_identity=True)['state']=='candidate'
                if not quiet:
                    record('reverse_displacement_or_endpoint_speed');continue
            record('candidate')
            yield dict(a=a,b=b,identity=identity,classes=[before['class_type'],after['class_type']],direction=before['direction'],
                stationary_noise_admission=quiet,
                requires_lateral_check=lateral>2,
                recording_gap=outage,frame_gap_basis=site.get('frame_gap_basis','receipt'),classification_changed=not same_class,missing_receipt_fraction=min(1.,missing/duration))
