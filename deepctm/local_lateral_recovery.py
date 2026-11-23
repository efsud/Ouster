"""Evidence-gated short same-ID lateral recovery, never identity guessing."""
from collections import defaultdict
from .same_id_gaps import candidates
from .lateral_gap import supports

def proposals(site,max_gap=10):
    # Use identical consecutive-fragment pairing as the established same-ID gate.
    groups=defaultdict(list)
    for tr in site['tracks']:
        key=tr.get('source_key',[])
        if len(key)==3:groups[tuple(key[:2])].append(tr)
    for identity,tracks in groups.items():
        tracks.sort(key=lambda tr:tr['points'][0][0])
        for before,after in zip(tracks,tracks[1:]):
            if before['class_type']!='2' or after['class_type']!='2':continue
            if not 1.5<after['points'][0][0]-before['points'][-1][0]<=max_gap:continue
            pair=dict(site,tracks=[before,after])
            old=list(candidates(pair,include_same_class=True))
            if old:continue
            for c in candidates(pair,include_same_class=True,allow_lateral_motion=True):
                if c['requires_lateral_check']:yield c,before,after

def reconstruct(site,predict,max_gap=10,audit=None):
    result=[]
    for c,before,after in proposals(site,max_gap):
        points=predict(c['a'],c['b'])
        if points is None:
            if audit is not None:audit('longitudinal_physics')
            continue
        ok,evidence=supports(before,after,points)
        if not ok:
            if audit is not None:audit(evidence['reason'])
            continue
        result.append(dict(site=site['id'],direction=c['direction'],class_type='2',points=points,source='inferred',
            method='kinematic_same_id_lateral_v1',identity='same_sensor_session_id',identity_key=list(c['identity']),
            object_id=c['identity'][1],gap_kind='supported_lateral_motion',gap_s=c['b']['t']-c['a']['t'],
            lateral_evidence=evidence,uncertainty='masked_local_validation_not_verified_lane_assignment'))
    return result
