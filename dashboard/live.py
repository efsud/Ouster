"""Project stored SDK frames to map coordinates without mutating sites."""
import time
from .analytics import local_to_geo

def snapshot(store, site, now=None):
    latest=store.latest(site['id'])
    base={'site':site['id'],'objects':[]}
    if not latest:
        return dict(base,state='unavailable',reason='No frames recorded for this site')
    base['timestamp']=latest['timestamp']
    age=(time.time() if now is None else now)-latest['timestamp']
    if age>5 or age< -5:
        return dict(base,state='stale',reason='No current frames within 5 seconds of this computer clock')
    origin=site.get('origin')
    if not origin or site.get('calibration_verified') is not True:
        return dict(base,state='uncalibrated',reason='Frames received; origin and rotation require verification')
    try:
        # Validate origin and rotation even when a valid frame contains no objects.
        local_to_geo(0,0,origin['lat'],origin['lng'],site['rotation_deg'])
    except (ValueError,KeyError,TypeError):
        return dict(base,state='uncalibrated',reason='Invalid origin or rotation in local site metadata')
    rejected=0
    for obj in latest['frame'].get('objects',[]):
        try:
            if not isinstance(obj,dict) or not isinstance(obj.get('id'),str) or not obj['id']:
                raise ValueError('Missing object id')
            # Proto3 omits default-valued scalar fields; absent centerX/Y means zero.
            lat,lng=local_to_geo(obj.get('centerX',0),obj.get('centerY',0),origin['lat'],origin['lng'],site['rotation_deg'])
            base['objects'].append({'id':obj['id'],'lat':lat,'lng':lng,'class':obj.get('classType','unknown')})
        except (ValueError,KeyError,TypeError):
            rejected+=1
    return dict(base,state='live',rejected_objects=rejected)
