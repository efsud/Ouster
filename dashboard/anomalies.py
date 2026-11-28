"""Explainable, provisional anomaly detection. No signal control or notifications."""
from datetime import datetime
from zoneinfo import ZoneInfo
from statistics import median
import hashlib
import json
import time

VERSION='rules-1'
METRICS=['control_delay','stopped_delay','queue_p95','volume','aog','split_failure','discharge']

def key(*parts):return hashlib.sha256('|'.join(map(str,parts)).encode()).hexdigest()[:24]

def qualified(row,metric):
    q=row['quality'];v=row['values'].get(metric)
    if row['source']=='synthetic' or v is None or q.get('coverage',0)<.8 or q.get('valid_tracks',0)<15:return False
    if metric in ['aog','split_failure','discharge'] and 'Signal clocks not verified' in q.get('flags',[]):return False
    if metric=='queue_p95' and q.get('visible_queue_samples',0)==0:return False
    return not any('Negative delay' in flag for flag in q.get('flags',[]))

def baseline(current,rows,metric,timezone):
    target=datetime.fromtimestamp(current['start'],ZoneInfo(timezone));values=[];days=set()
    for row in rows:
        if not current['start']-30*86400<=row['start']<current['start']:continue
        if row['site']!=current['site'] or row['approach']!=current['approach'] or row['source']!=current['source'] or row['end']-row['start']!=300:continue
        if row.get('provenance',{}).get('calibration_version')!=current.get('provenance',{}).get('calibration_version'):continue
        if not qualified(row,metric):continue
        local=datetime.fromtimestamp(row['start'],ZoneInfo(timezone))
        # Same 30-minute local-time band and weekday/weekend class, prior dates only.
        if local.date()>=target.date() or (local.weekday()<5)!=(target.weekday()<5):continue
        if (local.hour*60+local.minute)//30!=(target.hour*60+target.minute)//30:continue
        values.append(row['values'][metric]);days.add(local.date())
    if len(days)<10:return {'status':'insufficient_baseline','valid_days':len(days),'required_days':10}
    center=median(values);mad=median(abs(x-center) for x in values)
    if mad==0:return {'status':'zero_mad','median':center,'mad':0,'valid_days':len(days)}
    scale=1.4826*mad;value=current['values'][metric];z=(value-center)/scale
    return {'status':'outlier' if abs(z)>3.5 else 'normal','median':center,'mad':mad,'score':z,'expected_range':[center-3.5*scale,center+3.5*scale],'observed':value,'valid_days':len(days)}

def evaluate_traffic(store,site):
    rows=store.history(site=site['id'],limit=1000000,cadence='five_minute')
    rows=[r for r in rows if r['source']!='synthetic' and r['end']-r['start']==300]
    rows.sort(key=lambda r:(r['approach'],r['start'],r['source']))
    groups={};timezone=site.get('timezone','America/Toronto')
    def group(row):
        d=datetime.fromtimestamp(row['start'],ZoneInfo(timezone))
        return (row['approach'],(d.hour*60+d.minute)//30,d.weekday()<5)
    for row in rows:groups.setdefault(group(row),[]).append(row)
    previous={};generated=[]
    for r in rows:
        for metric in METRICS+['queue_storage']:
            token=(r['approach'],metric)
            underlying='queue_p95' if metric=='queue_storage' else metric
            evaluation={'status':'suppressed_quality'}
            if qualified(r,underlying):
                if metric=='queue_storage':
                    lane=next((a for a in site.get('scene',{}).get('approaches',[]) if a['id']==r['approach']),{})
                    storage=lane.get('storage_m')
                    if lane.get('storage_verified') is True and isinstance(storage,(float,int)) and storage>0:
                        evaluation={'status':'outlier' if r['values']['queue_p95']>=.9*storage else 'normal','observed':r['values']['queue_p95'],'expected_range':[0,.9*storage],'threshold':.9*storage}
                    else:evaluation={'status':'unverified_storage'}
                else:evaluation=baseline(r,groups[group(r)],metric,timezone)
            with store.connect() as db:
                db.execute('INSERT OR REPLACE INTO evaluations VALUES(?,?,?,?,?,?)',(r['site'],r['approach'],r['start'],metric,evaluation['status'],json.dumps(evaluation)))
            prev=previous.get(token)
            outlier=evaluation['status']=='outlier'
            direction=1 if metric=='queue_storage' else (1 if evaluation.get('score',0)>0 else -1)
            adjacent=prev and prev['row']['end']==r['start'] and prev['row']['source']==r['source']
            if outlier and adjacent and prev['outlier'] and prev['direction']==direction:
                identifier=prev.get('episode') or key(r['site'],r['approach'],metric,prev['row']['start'],VERSION)
                a={'id':identifier,'site':r['site'],'approach':r['approach'],'category':'traffic','rule':metric,'severity':'warning','start':prev.get('episode_start',prev['row']['start']),'end':r['end'],'state':'active','evidence':dict(evaluation,version=VERSION,validation='provisional',quality=r['quality'],source=r['source'],window_start=r['start'],window_end=r['end'])}
                store.save_anomaly(a);generated.append(a)
                previous[token]={'row':r,'outlier':True,'direction':direction,'episode':identifier,'episode_start':a['start']}
            else:
                if prev and prev.get('episode'):
                    with store.connect() as db:db.execute('UPDATE anomalies SET state=? WHERE id=?',('resolved' if adjacent and evaluation['status']=='normal' else 'unknown',prev['episode']))
                previous[token]={'row':r,'outlier':outlier,'direction':direction}
    return generated

def evaluate_health(store,site,now=None):
    now=time.time() if now is None else now;health=store.health(site['id']);latest=store.latest(site['id'])
    findings=[]
    if health.get('error'):findings.append((health['error'],{'error':health['error'],'collector_state':health['state']}))
    receipt=health.get('last_receipt')
    if receipt is not None and now-receipt>5:findings.append(('stale_stream',{'last_receipt':receipt,'age_s':now-receipt}))
    if latest and latest['timestamp']>now+5:findings.append(('future_timestamp',{'sensor_time':latest['timestamp']}))
    if latest:
        invalid=0
        import math
        for obj in latest['frame'].get('objects',[]):
            try:
                x,y=float(obj.get('centerX',0)),float(obj.get('centerY',0))
                if not math.isfinite(x+y) or math.hypot(x,y)>5000:invalid+=1
            except (ValueError,TypeError,AttributeError):invalid+=1
        if invalid:findings.append(('invalid_coordinates',{'rejected_objects':invalid,'sensor_time':latest['timestamp']}))
    windows=store.history(site=site['id'],start=now-600,limit=1000,cadence='five_minute')
    for r in windows:
        if r['source']!='synthetic' and r['quality'].get('coverage',0)<.8:
            findings.append(('inadequate_coverage',{'coverage':r['quality']['coverage'],'window_start':r['start'],'approach':r['approach']}));break
    active={rule for rule,_ in findings}
    with store.connect() as db:
        old=db.execute("SELECT * FROM anomalies WHERE site=? AND category='data_quality' AND state='active'",(site['id'],)).fetchall()
    for row in old:
        if row['rule'] not in active:
            with store.connect() as db:db.execute("UPDATE anomalies SET state='resolved',end=? WHERE id=?",(now,row['id']))
    for rule,evidence in findings:
        existing=next((a for a in old if a['rule']==rule),None)
        begin=existing['start'] if existing else now
        store.save_anomaly({'id':existing['id'] if existing else key(site['id'],rule,begin),'site':site['id'],'category':'data_quality','rule':rule,'start':begin,'end':now,'evidence':dict(evidence,version=VERSION,validation='provisional')})
