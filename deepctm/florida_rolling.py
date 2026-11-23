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
    db.execute('CREATE TABLE IF NOT EXISTS phase_samples(site TEXT,session TEXT,received REAL,payload TEXT,PRIMARY KEY(site,session,received))')
    db.execute('CREATE TABLE IF NOT EXISTS ingestion_epochs(start REAL PRIMARY KEY,mode TEXT)')
    return db

def purge(db,now):
    db.execute('DELETE FROM frames WHERE received < ?',(now-RETENTION,))
    db.execute('DELETE FROM phase_samples WHERE received < ?',(now-RETENTION,));db.commit()

def geometry(sites,road_axes=None):
    sites=sorted(sites,key=lambda s:s['reference_location']['lng']);station=0;out=[]
    for i,s in enumerate(sites):
        origin=s['reference_location']
        if i:
            old=sites[i-1]['reference_location'];station+=math.hypot((origin['lng']-old['lng'])*111320*math.cos(math.radians(origin['lat'])),(origin['lat']-old['lat'])*111320)
        a=sites[max(0,i-1)]['reference_location'];b=sites[min(len(sites)-1,i+1)]['reference_location']
        bearing=math.atan2(b['lat']-a['lat'],(b['lng']-a['lng'])*math.cos(math.radians(origin['lat'])))
        axis=(road_axes or {}).get('sites',{}).get(s['id'])
        if axis is not None:bearing=math.radians(axis['bearing_deg'])
        out.append(dict(s,station_m=station,bearing=bearing,trajectory_road_segments=axis.get('segments_xy') if axis else None))
    return out

def build(db,sites,end,track_observer=None,road_axes=None,time_basis="receipt",retain_stationary_context=False,processing_interval_s=0.,merge_vehicle_classes=False):
    if time_basis not in ("receipt","sensor_elapsed"):raise ValueError("Unknown time basis")
    start=end-WINDOW;output=[]
    for s in geometry(sites,road_axes):
        from dashboard.movements import TrackCollector
        movements=TrackCollector() if s.get('region') in ('Florida','Toronto') else None
        from collections import Counter
        breaks=Counter()
        active={};tracks=[];chunks={};epochs={};identity_class={};vehicle_keys={};local_estimates=[];receipt_gaps=[];first=None;last=None;frames=0;coverage=[set() for _ in range(60)]
        def flush(key,break_chain=True):
            points=active.pop(key,[])
            epoch=epochs.get(key,0)
            if break_chain:epochs[key]=epoch+1
            if len(points)<3:return
            net=points[-1][1]-points[0][1];travel=sum(abs(b[1]-a[1]) for a,b in zip(points,points[1:]))
            if points[-1][0]-points[0][0]<2:return
            stationary=abs(net)<3 or abs(net)<.7*travel
            if stationary:
                if not retain_stationary_context or key[2] not in {'1','2','3','4','5','6','7','8','9','15'}:return
                if max(p[1] for p in points)-min(p[1] for p in points)>2 or max(p[2] for p in points)-min(p[2] for p in points)>1:return
            if not stationary:chunks.setdefault((key,epoch),[]).append(points)
            if track_observer is not None:track_observer(s,key,points)
            from statistics import median
            from .endpoint_context import select
            first_context=select(points,False);last_context=select(points,True)
            class_counts=Counter(p[7] for p in points)
            displayed_class=class_counts.most_common(1)[0][0]
            tracks.append({'observed_class_counts':dict(class_counts),'stationary_context':stationary,'source_key':list(key),'receipt_start':points[0][0],'receipt_end':points[-1][0],
                'lateral_start_m':median(p[2] for p in first_context),'lateral_end_m':median(p[2] for p in last_context),
                'sensor_start':points[0][4].isoformat(),'sensor_end':points[-1][4].isoformat(),
                'original_receipt_start':points[0][5],'original_receipt_end':points[-1][5],
                'class_type':displayed_class,'direction':'eastbound' if net>0 else 'westbound','points':[[round(p[0]-start,2),round(p[1]+s['station_m'],2),round(p[3],2)] for p in points]})
            from .object_shape import summarize as summarize_shape
            sizes=[p[6] for p in points]
            tracks[-1].update(dimensions=sizes,shape_start=summarize_shape(sizes[:5]),shape_end=summarize_shape(sizes[-5:]))
            tracks[-1].update(lateral_start_context=[[round(p[0]-start,2),p[2]] for p in first_context],
                              lateral_end_context=[[round(p[0]-start,2),p[2]] for p in last_context])
            if time_basis=='sensor_elapsed':tracks[-1]['original_receipt_offsets_s']=[round(p[5]-start,6) for p in points]
        angle=math.radians(s.get('preview_rotation_deg',220))-s['bearing'];c=math.cos(angle);sn=math.sin(angle)
        source_rows=db.execute('SELECT session,received,payload FROM frames WHERE site=? AND received>=? AND received<=? ORDER BY received',(s['id'],start,end)).fetchall()
        raw_receipts=[r[1] for r in source_rows]
        original_gaps=[[a-start,b-start] for a,b in zip(raw_receipts,raw_receipts[1:]) if b-a>1.5]
        seen_payloads=set();unique_rows=[]
        for row in source_rows:
            signature=(row[0],row[2])
            if signature not in seen_payloads:unique_rows.append(row);seen_payloads.add(signature)
        duplicate_frames=len(source_rows)-len(unique_rows)
        clock_audit=[]
        if time_basis=='sensor_elapsed':
            from .event_clock import align_frames
            processing_rows,clock_audit=align_frames(unique_rows)
            for audit in clock_audit:
                audit['outside_display_window']=sum(session==audit['session'] and not start<=t<=end for session,t,_,_ in processing_rows)
            processing_rows=[row for row in processing_rows if start<=row[1]<=end]
        else:processing_rows=[(*row,row[1]) for row in unique_rows]
        from .frame_sampling import sample
        processing_rows=sample(processing_rows,processing_interval_s)
        for session,receipt,payload,original_receipt in processing_rows:
            e=json.loads(payload);frames+=1;first=first or receipt
            if last is not None and receipt-last>1.5:receipt_gaps.append([last-start,receipt-start])
            last=receipt
            second=int(receipt-start)
            if 0<=second<3600:coverage[second//60].add(second%60)
            try:stamp=datetime.fromisoformat(e.get('frame',{}).get('timestamp') or e['timestamp'])
            except (ValueError,KeyError,TypeError):continue
            for o in e.get('frame',{}).get('objects',[]):
                if not o.get('id'):continue
                actual_class=str(o.get('classType','unknown'))
                key=(session,str(o['id']),actual_class)
                if merge_vehicle_classes and actual_class in {'1','2','3','4','5','6','7','8','9','15'}:
                    key=vehicle_keys.setdefault(key[:2],key)
                if movements is not None:
                    previous_class=identity_class.get(key[:2])
                    if previous_class is not None and previous_class!=key[2]:
                        # A label change is not a new identity. End the old
                        # displayed fragment so class-specific tracks cannot
                        # overlap by silently skipping intervening observations.
                        breaks['classification_change']+=1
                        flush((*key[:2],previous_class),break_chain=False)
                    identity_class[key[:2]]=key[2]
                try:x=float(o.get('centerX',0));y=float(o.get('centerY',0))*(-1 if s.get('preview_mirror_y') else 1)
                except (ValueError,TypeError):continue
                along=c*x-sn*y;across=sn*x+c*y
                if movements is not None and key[2] in {'1','2','3','4','5','6','7','8','9','15'}:movements.feed(key,receipt,along,across)
                from .road_axes import road_contains
                in_road=road_contains(along,across,s['trajectory_road_segments']) if s.get('trajectory_road_segments') else abs(across)<=18
                if not math.isfinite(along+across) or abs(along)>120 or not in_road:
                    if key in active:breaks['outside_display_geometry']+=1
                    flush(key);continue
                old=active.get(key);speed=0
                if old:
                    try:dt=(stamp-old[-1][4]).total_seconds()
                    except TypeError:dt=0
                    dr=receipt-old[-1][0]
                    if not(0<dt<=3 and 0<dr<=3 and .5<=dt/dr<=2):
                        breaks['long_time_gap' if dt>3 or dr>3 else 'clock_order_or_receipt_jitter']+=1
                        flush(key,break_chain=not(3<dr<=30 and .8<=dt/dr<=1.2))
                    else:
                        speed=math.hypot(along-old[-1][1],across-old[-1][2])/dt
                        if speed>60:breaks['speed_outlier']+=1;flush(key);speed=0
                from .object_shape import dimensions
                active.setdefault(key,[]).append((receipt,along,across,speed,stamp,original_receipt,dimensions(o),actual_class))
            if movements is not None:movements.expire(receipt)
            for key in list(active):
                if receipt-active[key][-1][0]>3:
                    breaks['object_absent_over_three_seconds']+=1;flush(key,break_chain=False)
        for key in list(active):flush(key)
        from .local_gaps import bridge,gap_evidence,VEHICLES
        local_candidates=[]
        for (key,epoch),parts in chunks.items():
            if key[2] not in VEHICLES:continue
            for before,after in zip(parts,parts[1:]):
                evidence=gap_evidence(before,after,road_roi=bool(s.get('trajectory_road_segments')))
                if evidence is not None:
                    for ep in ('a','b'):
                        evidence[ep]['t']-=start;evidence[ep]['x']+=s['station_m']
                    local_candidates.append(dict(evidence,source_key=list(key),class_type=key[2],epoch=epoch))
                estimated=bridge(before,after)
                if estimated is not None:
                    local_estimates.append({'class_type':key[2],'direction':'eastbound' if estimated[-1][1]>=estimated[0][1] else 'westbound',
                        'gap_seconds':after[0][0]-before[-1][0], 'method':'motion-constrained local Hermite interpolation',
                        'points':[[round(t-start,2),round(x+s['station_m'],2),round(v,2)] for t,x,v in estimated]})
        if retain_stationary_context:
            from .stationary_context import attach
            tracks=attach(tracks)
        movement_summary=None
        if movements is not None:
            from dashboard.movement_phases import summarize
            complete=movements.finish();by_key={}
            for full in complete:by_key.setdefault(full['key'],[]).append(full)
            for tr in tracks:
                candidates=[full for full in by_key.get(tuple(tr['source_key']),[]) if full['start']<=tr['receipt_start'] and full['end']>=tr['receipt_end']]
                tr['movement']=candidates[0]['movement'] if len(candidates)==1 else {'state':'unknown','can_match_next':False,'can_match_previous':False}
            tracks=[tr for tr in tracks if tr['movement'].get('state')=='unknown' or tr['direction'] in (tr['movement'].get('incoming_direction'),tr['movement'].get('outgoing_direction'))]
            try:phase_rows=db.execute('SELECT received,session,payload FROM phase_samples WHERE site=? AND received>=? AND received<=? ORDER BY received',(s['id'],start,end)).fetchall()
            except sqlite3.OperationalError:phase_rows=[]
            # Do not correlate receipt-timed phases with a different observation clock.
            if time_basis!='receipt':phase_rows=[]
            movement_summary=summarize(complete,phase_rows)
            mapping={m['movement']:m for m in movement_summary['movements']}
            for tr in tracks:
                evidence=mapping.get(tr['movement'].get('movement'),{})
                tr['movement']['phase_numbers']=evidence.get('phase_numbers',[])
                tr['movement']['phase_mapping']=evidence.get('phase_mapping','insufficient_or_ambiguous')
        output.append({'movement_summary':movement_summary,'id':s['id'],'name':s['name'],'station_m':s['station_m'],'projection_bearing_deg':math.degrees(s['bearing']),'frames':frames,'first_receipt':raw_receipts[0] if raw_receipts else None,'last_receipt':raw_receipts[-1] if raw_receipts else None,'first_observation_time':first,'last_observation_time':last,'raw_frames':len(source_rows),'duplicate_frame_payloads':duplicate_frames,'fragment_break_reasons':dict(breaks),'coverage_basis':time_basis,'receipt_gaps':original_gaps,'observation_gaps':receipt_gaps,'frame_gap_basis':time_basis,'clock_audit':clock_audit,'tracks':tracks,'local_estimates':local_estimates,'local_gap_candidates':local_candidates,'coverage':[len(v)/60 for v in coverage]})
    try:
        ingestion_epochs=[{'start':r[0],'mode':r[1]} for r in db.execute('SELECT start,mode FROM ingestion_epochs WHERE start<=? ORDER BY start',(end,))]
        ingestion_epochs=[r for i,r in enumerate(ingestion_epochs) if r['start']>=start or i==len(ingestion_epochs)-1 or ingestion_epochs[i+1]['start']>start]
    except sqlite3.OperationalError:ingestion_epochs=[]
    timeline_note='receipt time' if time_basis=='receipt' else 'experimental sensor elapsed time; absolute synchronization unverified'
    result={'time_basis':time_basis,'geometry_version':((road_axes or {}).get('version','inter-sensor-chord-v1') if any(s['id'] in (road_axes or {}).get('sites',{}) for s in sites) else 'inter-sensor-chord-v1'),'generated_at':end,'start':start,'end':end,'next_update':end+REFRESH,'retention_seconds':RETENTION,'sample_interval_s':None,'ingestion_epochs':ingestion_epochs,'endpoint_context_version':'visible-minimum-one-second-v1','stationary_context_enabled':retain_stationary_context,'processing_interval_s':processing_interval_s,'merge_vehicle_classes':merge_vehicle_classes,'sites':output,'note':f'Sampled local trajectory fragments; provisional alignment and {timeline_note}. No cross-sensor identity matching.'}
    from .rolling_estimates import gap_validation
    from .transform_manifest import manifest
    result['transform_manifest']=manifest(sites)
    result['estimates']={'method':'Local within-track interpolation only','links':[]};result['gap_validation']=gap_validation(result)
    if sites and sites[0].get('region')=='Florida':
        from .spatial_bridges import reconstruct
        result['spatial_estimates']=reconstruct(result)
    return result

def read_snapshot(now=None,folder=None):
    folder=FOLDER if folder is None else folder
    now=time.time() if now is None else now
    try:
        p=json.loads((folder/'snapshot.json').read_text())
        # Do not serve a cached hour outside the 90-minute retention horizon.
        if p['start']<now-RETENTION:return {'state':'expired','message':'Snapshot expired; rolling collector must be running.'}
        p['estimates']={'method':'Local within-track interpolation only','links':[]}
        p['state']='ready';return p
    except (OSError,ValueError):return {'state':'warming','message':'Collecting the first samples. Initial figure appears after about 30 seconds.'}

def main(region="Florida",folder=None,source_name="florida-live.sqlite3"):
    folder=FOLDER if folder is None else folder
    from dashboard.server import sites
    from concurrent.futures import ThreadPoolExecutor
    folder.mkdir(parents=True,exist_ok=True)
    # One writer prevents competing retention and snapshot schedules.
    import fcntl
    lock=open(folder/'writer.lock','w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    db=connect(folder/'buffer.sqlite3');source=sqlite3.connect(f'file:{ROOT}/data/{source_name}?mode=ro',uri=True)
    entries=[s for s in sites() if s['region']==region];ids={s['id'] for s in entries};begin=time.time();last_publish=0
    try:
        previous=json.loads((folder/'snapshot.json').read_text())
        last_publish=previous.get('next_update',previous['generated_at']+REFRESH)-REFRESH if 'estimates' in previous else 0
    except (OSError,ValueError,KeyError):pass
    # Expired snapshots need a fresh warm-up, not an immediate near-empty publication.
    if last_publish and begin-last_publish>REFRESH:last_publish=0
    purge(db,begin)
    pool=ThreadPoolExecutor(max_workers=1);pending=None
    def compute(end):
        reader=sqlite3.connect(f'file:{folder}/buffer.sqlite3?mode=ro',uri=True,timeout=20)
        try:
            axis_path=ROOT/'config/reconstruction/corridor-road-axes.json'
            axes=json.loads(axis_path.read_text()) if axis_path.exists() else None
            journal_config=ROOT/'config/reconstruction/frame-journal.json'
            processing_interval=json.loads(journal_config.read_text()).get('figure_processing_interval_s',0.) if journal_config.exists() else 0.
            return build(reader,entries,end,road_axes=axes,processing_interval_s=processing_interval)
        finally:reader.close()
    phase_saved={}
    journal_path=ROOT/'config/reconstruction/frame-journal.json'
    journal_enabled=journal_path.exists() and region.lower() in json.loads(journal_path.read_text()).get('enabled_regions',[])
    mode='frame_journal' if journal_enabled else 'latest_preview_poll'
    prior_mode=db.execute('SELECT mode FROM ingestion_epochs ORDER BY start DESC LIMIT 1').fetchone()
    if prior_mode is None or prior_mode[0]!=mode:
        db.execute('INSERT INTO ingestion_epochs VALUES(?,?)',(begin,mode));db.commit()
    journal_cursor=0;journal_lease=0;journal_rows=0
    while True:
        now=time.time()
        if journal_enabled:
            from .frame_journal import install,copy_batch
            if now>=journal_lease:
                writer=sqlite3.connect(ROOT/'data'/source_name,timeout=20)
                try:install(writer,now+90)
                finally:writer.close()
                journal_lease=now+30
            journal_cursor,count=copy_batch(source,db,ids,journal_cursor,now)
            journal_rows+=count
        # Bootstrap/fallback only: journal replay is idempotent against preview.
        for site,session,key,receipt,payload in source.execute('SELECT site,session,event_key,received_at,payload FROM preview_frames'):
            if site in ids and 0<=now-receipt<=3:
                db.execute('INSERT OR IGNORE INTO frames VALUES(?,?,?,?,?)',(site,session,key,receipt,payload))
        if region=='Florida':
            for phase_site,payload in source.execute('SELECT site,payload FROM live_signal_state'):
                if phase_site not in ids:continue
                try:
                    raw=json.loads(payload);session=raw.get('session','');phases={n:{'status':p.get('status'),'received_at':p.get('received_at')} for n,p in raw.get('phases',{}).items() if p.get('status') in ('GREEN','RED','YELLOW')}
                    compact=json.dumps({'initialized':raw.get('initialized',False),'phases':phases},sort_keys=True)
                    prior=phase_saved.get(phase_site)
                    if prior is None or prior[0]!=compact or now-prior[1]>=5:
                        db.execute('INSERT OR IGNORE INTO phase_samples VALUES(?,?,?,?)',(phase_site,session,now,compact));phase_saved[phase_site]=(compact,now)
                except (ValueError,TypeError):continue
        purge(db,now)
        if pending is not None and pending.done():
            result=pending.result();temp=folder/'snapshot.tmp';temp.write_text(json.dumps(result,allow_nan=False));temp.replace(folder/'snapshot.json');pending=None
        requested=(folder/'refresh.request').exists()
        if pending is None and (requested or (not last_publish and now-begin>=30) or (last_publish and now>=last_publish+REFRESH)):
            if requested:(folder/'refresh.request').unlink(missing_ok=True)
            pending=pool.submit(compute,now);last_publish=now
        health={'ingestion':'frame_journal' if journal_enabled else 'latest_preview_poll','journal_rows_copied':journal_rows,'journal_cursor':journal_cursor,'updated_at':time.time(),'buffer_start':db.execute('SELECT min(received) FROM frames').fetchone()[0],'buffer_end':db.execute('SELECT max(received) FROM frames').fetchone()[0],'next_update':last_publish+REFRESH if last_publish else begin+30}
        temp=folder/'status.tmp';temp.write_text(json.dumps(health));temp.replace(folder/'status.json')
        time.sleep(.5)

if __name__=='__main__':main()
