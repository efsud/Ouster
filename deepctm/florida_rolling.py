"""Bounded Florida trajectory buffer and half-hourly one-hour figure snapshots."""
import json,math,sqlite3,time,os
from pathlib import Path
from datetime import datetime
ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'data/florida-rolling'
RETENTION=5400
WINDOW=3600
REFRESH=1800

def connect(path):
    db=sqlite3.connect(path,timeout=20)
    db.execute('PRAGMA secure_delete=ON')
    db.execute('CREATE TABLE IF NOT EXISTS frames(site TEXT,session TEXT,event_key TEXT,received REAL,payload TEXT,PRIMARY KEY(site,session,event_key))')
    db.execute('CREATE INDEX IF NOT EXISTS received_idx ON frames(received)')
    db.execute('CREATE INDEX IF NOT EXISTS site_received_idx ON frames(site,received)')
    return db

def purge(db,now):
    db.execute('DELETE FROM frames WHERE received < ?',(now-RETENTION,));db.commit()

def geometry(sites):
    sites=sorted(sites,key=lambda s:s['reference_location']['lng']);station=0;out=[]
    for i,s in enumerate(sites):
        origin=s['reference_location']
        if i:
            old=sites[i-1]['reference_location'];station+=math.hypot((origin['lng']-old['lng'])*111320*math.cos(math.radians(origin['lat'])),(origin['lat']-old['lat'])*111320)
        a=sites[max(0,i-1)]['reference_location'];b=sites[min(len(sites)-1,i+1)]['reference_location']
        bearing=math.atan2(b['lat']-a['lat'],(b['lng']-a['lng'])*math.cos(math.radians(origin['lat'])))
        out.append(dict(s,station_m=station,bearing=bearing))
    return out

def build(db,sites,end):
    start=end-WINDOW;output=[]
    for s in geometry(sites):
        active={};tracks=[];first=None;last=None;frames=0
        def flush(key):
            points=active.pop(key,[])
            if len(points)<3:return
            net=points[-1][1]-points[0][1];travel=sum(abs(b[1]-a[1]) for a,b in zip(points,points[1:]))
            if points[-1][0]-points[0][0]<2 or abs(net)<3 or abs(net)<.7*travel:return
            tracks.append({'class_type':key[2],'direction':'eastbound' if net>0 else 'westbound','points':[[round(p[0]-start,2),round(p[1]+s['station_m'],2),round(p[3],2)] for p in points]})
        angle=math.radians(s.get('preview_rotation_deg',220))-s['bearing'];c=math.cos(angle);sn=math.sin(angle)
        for session,receipt,payload in db.execute('SELECT session,received,payload FROM frames WHERE site=? AND received>=? AND received<=? ORDER BY received',(s['id'],start,end)):
            e=json.loads(payload);frames+=1;first=first or receipt;last=receipt
            try:stamp=datetime.fromisoformat(e.get('frame',{}).get('timestamp') or e['timestamp'])
            except (ValueError,KeyError,TypeError):continue
            for o in e.get('frame',{}).get('objects',[]):
                if not o.get('id'):continue
                key=(session,str(o['id']),str(o.get('classType','unknown')))
                try:x=float(o.get('centerX',0));y=float(o.get('centerY',0))*(-1 if s.get('preview_mirror_y') else 1)
                except (ValueError,TypeError):continue
                along=c*x-sn*y;across=sn*x+c*y
                if not math.isfinite(along+across) or abs(along)>120 or abs(across)>18:flush(key);continue
                old=active.get(key);speed=0
                if old:
                    try:dt=(stamp-old[-1][4]).total_seconds()
                    except TypeError:dt=0
                    dr=receipt-old[-1][0]
                    if not(0<dt<=3 and 0<dr<=3 and .5<=dt/dr<=2):flush(key)
                    else:
                        speed=math.hypot(along-old[-1][1],across-old[-1][2])/dt
                        if speed>60:flush(key);speed=0
                active.setdefault(key,[]).append((receipt,along,across,speed,stamp))
            for key in list(active):
                if receipt-active[key][-1][0]>3:flush(key)
        for key in list(active):flush(key)
        output.append({'id':s['id'],'name':s['name'],'station_m':s['station_m'],'frames':frames,'first_receipt':first,'last_receipt':last,'tracks':tracks})
    return {'generated_at':end,'start':start,'end':end,'next_update':end+REFRESH,'retention_seconds':RETENTION,'sample_interval_s':.5,'sites':output,'note':'Sampled local trajectory fragments; provisional alignment and receipt time. No cross-sensor identity matching or inferred paths.'}

def read_snapshot(now=None,folder=None):
    folder=FOLDER if folder is None else folder
    now=time.time() if now is None else now
    try:
        p=json.loads((folder/'snapshot.json').read_text())
        # Do not serve a cached hour outside the 90-minute retention horizon.
        if p['start']<now-RETENTION:return {'state':'expired','message':'Snapshot expired; rolling collector must be running.'}
        p['state']='ready';return p
    except (OSError,ValueError):return {'state':'warming','message':'Collecting the first samples. Initial figure appears after about 30 seconds.'}

def main(region="Florida",folder=None,source_name="florida-live.sqlite3"):
    folder=FOLDER if folder is None else folder
    from dashboard.server import sites
    folder.mkdir(parents=True,exist_ok=True)
    # One writer prevents competing retention and snapshot schedules.
    import fcntl
    lock=open(folder/'writer.lock','w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    db=connect(folder/'buffer.sqlite3');source=sqlite3.connect(f'file:{ROOT}/data/{source_name}?mode=ro',uri=True)
    entries=[s for s in sites() if s['region']==region];ids={s['id'] for s in entries};begin=time.time();last_publish=0
    try:last_publish=json.loads((folder/'snapshot.json').read_text())['generated_at']
    except (OSError,ValueError,KeyError):pass
    purge(db,begin)
    while True:
        now=time.time()
        for site,session,key,receipt,payload in source.execute('SELECT site,session,event_key,received_at,payload FROM preview_frames'):
            if site in ids and 0<=now-receipt<=3:
                db.execute('INSERT OR IGNORE INTO frames VALUES(?,?,?,?,?)',(site,session,key,receipt,payload))
        purge(db,now)
        if (not last_publish and now-begin>=30) or (last_publish and now>=last_publish+REFRESH):
            result=build(db,entries,now);temp=folder/'snapshot.tmp';temp.write_text(json.dumps(result,allow_nan=False));temp.replace(folder/'snapshot.json');last_publish=now
        health={'updated_at':time.time(),'buffer_start':db.execute('SELECT min(received) FROM frames').fetchone()[0],'buffer_end':db.execute('SELECT max(received) FROM frames').fetchone()[0],'next_update':last_publish+REFRESH if last_publish else begin+30}
        temp=folder/'status.tmp';temp.write_text(json.dumps(health));temp.replace(folder/'status.json')
        time.sleep(.5)

if __name__=='__main__':main()
