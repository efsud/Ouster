"""Project stored SDK frames to map coordinates without mutating sites."""
import time
from .analytics import local_to_geo
from .calibration import report

def snapshot(store, site, now=None):
    latest=store.latest(site['id'])
    health=store.health(site['id'])
    clock=time.time() if now is None else now
    if health.get('state')=='receiving' and health.get('last_receipt') is not None and clock-health['last_receipt']>5:
        health=dict(health,state='stale')
    base={'site':site['id'],'objects':[],'health':health,'calibration':report(site),'server_time':time.time() if now is None else now}
    with store.connect() as db:
        base['active_anomalies']=db.execute("SELECT count(*) FROM anomalies WHERE site=? AND state='active'",(site['id'],)).fetchone()[0]
    if not latest:
        if health.get('saved_count',0)>0:
            return dict(base,state='clock_pending',reason='Raw events stored; sensor timezone requires verification. Approximate marker is an intersection reference only.')
        return dict(base,state='unavailable',reason=health.get('error') or 'No frames recorded for this site')
    base['timestamp']=latest['timestamp']
    base['received_at']=latest.get('received_at')
    base['event_key']=latest.get('event_key')
    age=(time.time() if now is None else now)-latest['timestamp']
    base['age_s']=age
    if age>5 or age< -5:
        return dict(base,state='stale',reason='No current frames within 5 seconds of this computer clock')
    origin=site.get('origin')
    if not origin or not base['calibration']['valid']:
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
            code=str(obj.get('classType','unknown'))
            kind='vehicle' if code in ['1','2','3','4','5','6','7','8','9','15'] else 'cyclist' if code in ['12','13','17'] else 'pedestrian' if code in ['0','10','11','14','16'] else 'unknown'
            base['objects'].append({'id':obj['id'],'lat':lat,'lng':lng,'class':code,'kind':kind,'timestamp':latest['timestamp'],'age_s':age})
        except (ValueError,KeyError,TypeError):
            rejected+=1
    return dict(base,state='live',rejected_objects=rejected)


def approximate_snapshot(store,site,now=None,rotation=None):
    """Receipt-timed visualization only; never promotes quarantined data to KPIs."""
    import json
    rotation=site.get('preview_rotation_deg',220) if rotation is None else rotation
    clock=time.time() if now is None else now
    base={'site':site['id'],'objects':[],'health':store.health(site['id']),
          'state':'unavailable','spatial_accuracy':'approximate','rotation_deg':rotation,
          'time_basis':'receipt; sensor timezone and upstream delay unverified'}
    with store.connect() as db:
        row=db.execute('SELECT * FROM preview_frames WHERE site=?',(site['id'],)).fetchone()
    if not row:return dict(base,reason='Waiting for received frames')
    base.update(event_key=row['event_key'],received_at=row['received_at'],age_s=clock-row['received_at'],session=row['session'])
    if not 0<=base['age_s']<=5:return dict(base,state='stale',reason='No receipt within five seconds')
    origin=site.get('reference_location')
    if not origin:return dict(base,reason='No approximate reference location')
    event=json.loads(row['payload']);base['sensor_timestamp_text']=event.get('timestamp')
    for obj in event.get('frame',{}).get('objects',[]):
        try:
            if not isinstance(obj.get('id'),str) or not obj['id']:continue
            lat,lng=local_to_geo(obj.get('centerX',0),obj.get('centerY',0),origin['lat'],origin['lng'],rotation)
            code=str(obj.get('classType','unknown'))
            kind='vehicle' if code in ['1','2','3','4','5','6','7','8','9','15'] else 'cyclist' if code in ['12','13','17'] else 'pedestrian' if code in ['0','10','11','14','16'] else 'unknown'
            base['objects'].append({'id':obj['id'],'lat':lat,'lng':lng,'kind':kind,'age_s':base['age_s'],'timestamp':row['received_at']})
        except (ValueError,KeyError,TypeError,AttributeError):continue
    return dict(base,state='approximate',reason='Live receipts · approximate origin and rotation · upstream delay unverified')
