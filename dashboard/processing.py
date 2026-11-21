"""Geometry-gated processing of archived SDK observations into KPI windows.

No geometry or clock mapping is inferred from an intersection name. Station is
arc length along an approach centerline; the last point is the stop line.
"""
import math
from collections import defaultdict
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from .analytics import calculate, finite
from .calibration import report

VERSION='trajectory-1'
VEHICLES={'1','2','3','4','5','6','7','8','9','15'}


def inside(point,polygon):
    x,y=point;hit=False
    for (ax,ay),(bx,by) in zip(polygon,polygon[1:]+polygon[:1]):
        if (ay>y)!=(by>y) and x<(bx-ax)*(y-ay)/(by-ay)+ax:hit=not hit
    return hit


def station(point,line):
    best=None;offset=0
    for i,(a,b) in enumerate(zip(line,line[1:])):
        dx,dy=b[0]-a[0],b[1]-a[1];length=math.hypot(dx,dy)
        if length==0:raise ValueError('Centerline contains duplicate consecutive points')
        u=((point[0]-a[0])*dx+(point[1]-a[1])*dy)/(length*length)
        clamped=max(0,min(1,u));distance=math.hypot(point[0]-a[0]-clamped*dx,point[1]-a[1]-clamped*dy)
        extended=u if (i==0 and u<0) or (i==len(line)-2 and u>1) else clamped
        candidate=(distance,offset+extended*length)
        if best is None or candidate[0]<best[0]:best=candidate
        offset+=length
    return best[1],offset


def validate_scene(site):
    calibration=report(site)
    if not calibration['valid']:raise ValueError('Verified calibration required: '+'; '.join(calibration['reasons']))
    scene=site.get('scene',{})
    if scene.get('verified') is not True or not scene.get('version') or not scene.get('reference'):
        raise ValueError('Verified, versioned scene geometry and reference required')
    approaches=scene.get('approaches',[])
    if not approaches:raise ValueError('No approach geometry configured')
    names=set()
    for a in approaches:
        if not isinstance(a.get('id'),str) or not a['id'] or a['id'] in names:raise ValueError('Unique approach IDs required')
        names.add(a['id'])
        for key,minimum in [('centerline',2),('analysis_polygon',3),('queue_polygon',3)]:
            if not isinstance(a.get(key),list) or len(a[key])<minimum:raise ValueError(f'{key} geometry missing')
            for p in a[key]:
                if not isinstance(p,list) or len(p)!=2:raise ValueError('Geometry points must be [x,y] metres')
                for v in p:finite(v,'geometry coordinate')
        _,length=station(a['centerline'][0],a['centerline'])
        if length<=0:raise ValueError('Positive approach length required')
        finite(a['free_speed_mps'],'free_speed_mps',.01);finite(a['lanes'],'lanes',1)
        if a['lanes']!=int(a['lanes']):raise ValueError('Lane count must be an integer')
        lane_polygons=a.get('lane_polygons',[a['analysis_polygon']] if a['lanes']==1 else [])
        if len(lane_polygons)!=a['lanes']:raise ValueError('Each lane needs a separate polygon for queue membership')
        for polygon in lane_polygons:
            if len(polygon)<3:raise ValueError('Each lane polygon needs at least three points')
            for point in polygon:
                if len(point)!=2:raise ValueError('Lane points must be [x,y]')
                for v in point:finite(v,'lane coordinate')
        finite(a.get('exit_offset_m',3),'exit_offset_m',0)
        finite(a.get('max_queue_gap_m',12),'max_queue_gap_m',.01)
    return scene


def crossing(previous,current,boundary):
    t0,s0=previous;t1,s1=current
    return t0+(boundary-s0)/(s1-s0)*(t1-t0) if s0<boundary<=s1 else None


def calendar_bounds(day,timezone='America/Toronto'):
    zone=ZoneInfo(timezone);start=datetime.fromisoformat(day).replace(tzinfo=zone)
    if start.hour or start.minute or start.second:raise ValueError('Use a local calendar date YYYY-MM-DD')
    return start.timestamp(),(start+timedelta(days=1)).timestamp()


def build_window(site,records,start,end):
    scene=validate_scene(site)
    if end<=start:raise ValueError('Positive reporting interval required')
    records=sorted([r for r in records if r.get('sensor_time') is not None and r.get('status')=='received'],key=lambda r:(r['sensor_time'],r['sequence']))
    frames=[r for r in records if 'frame' in r['payload']]
    sessions={r['session'] for r in frames if start<=r['sensor_time']<end}
    # Never stitch identities across a collector restart without validated association.
    reset_within=len(sessions)>1
    frame_times=sorted(set(r['sensor_time'] for r in frames))
    coverage_intervals=[]
    for a,b in zip(frame_times,frame_times[1:]):
        if 0<b-a<=3 and max(start,a)<min(end,b):coverage_intervals.append((max(start,a),min(end,b)))
    coverage=sum(b-a for a,b in coverage_intervals)/(end-start)
    outputs=[]
    for approach in scene['approaches']:
        line=approach['centerline'];_,length=station(line[0],line)
        threshold=approach.get('stopped_threshold_mps',2.5)
        tracks=defaultdict(list);queue_frames={};ambiguous=0;unresolved_speed=set()
        for r in frames:
            t=r['sensor_time'];objects=r['payload']['frame'].get('objects',[])
            for obj in objects:
                if str(obj.get('classType')) not in VEHICLES or obj.get('id') is None:continue
                try:
                    x=finite(obj.get('centerX',0),'x');y=finite(obj.get('centerY',0),'y')
                except ValueError:continue
                candidates=[a for a in scene['approaches'] if inside((x,y),a['analysis_polygon'])]
                if len(candidates)!=1:
                    if len(candidates)>1:ambiguous+=1
                    continue
                if candidates[0]['id']!=approach['id']:continue
                s,_=station((x,y),line)
                lanes=[i for i,polygon in enumerate(approach.get('lane_polygons',[approach['analysis_polygon']])) if inside((x,y),polygon)]
                if len(lanes)!=1:ambiguous+=1;continue
                identity=(r['session'],str(obj['id']))
                tracks[identity].append({'t':t,'s':s,'x':x,'y':y,'lane':lanes[0],'queue_region':inside((x,y),approach['queue_polygon'])})
        annotated=[];stopped_by_time=defaultdict(list)
        for identity,samples in tracks.items():
            samples=sorted({p['t']:p for p in samples}.values(),key=lambda p:p['t'])
            # Split gaps; each new fragment is censored unless both boundaries observed.
            fragments=[];fragment=[]
            for p in samples:
                if fragment and p['t']-fragment[-1]['t']>3:fragments.append(fragment);fragment=[]
                fragment.append(p)
            if fragment:fragments.append(fragment)
            for index,points in enumerate(fragments):
                if points:unresolved_speed.add(points[0]['t'])
                entry=arrival=exit_time=None;stopped=0;had_stop=False;gaps=[]
                for prev,p in zip(points,points[1:]):
                    dt=p['t']-prev['t'];gaps.append(dt)
                    speed=math.hypot(p['x']-prev['x'],p['y']-prev['y'])/dt
                    for boundary,kind in [(0,'entry'),(length,'arrival'),(length+approach.get('exit_offset_m',3),'exit')]:
                        at=crossing((prev['t'],prev['s']),(p['t'],p['s']),boundary)
                        if at is None:continue
                        if kind=='entry' and entry is None:entry=at
                        if kind=='arrival' and arrival is None:arrival=at
                        if kind=='exit' and exit_time is None:exit_time=at
                    if speed<=threshold:
                        if entry is not None:
                            a=max(prev['t'],entry);b=min(p['t'],exit_time if exit_time is not None else p['t'])
                            stopped+=max(0,b-a)
                        if p['queue_region'] and 0<=p['s']<=length:
                            if prev['lane']==p['lane']:
                                stopped_by_time[p['t']].append((p['lane'],length-p['s']));had_stop=True
                annotated.append({'id':f"{site['id']}:{identity[0]}:{identity[1]}:{index}",'vehicle':True,'entry':entry,'arrival':arrival,'exit':exit_time,'complete':entry is not None and arrival is not None and exit_time is not None,'max_gap_s':max(gaps,default=0),'stopped_s':stopped if exit_time is not None else None,'green':None,'departed_from_queue_on_green':False,'was_queued':had_stop})
        # Queue membership is anchored at the stop line then chained by plausible gaps.
        max_gap=approach.get('max_queue_gap_m',12)
        for t in frame_times:
            tails=[]
            for lane in range(approach['lanes']):
                tail=0
                for distance in sorted(d for lane_id,d in stopped_by_time.get(t,[]) if lane_id==lane):
                    if distance-tail>max_gap:break
                    tail=distance
                tails.append(tail)
            queue_frames[t]=max(tails,default=0)
        # Uniform one-second grid. No zero queue for an unobserved time.
        queue_samples=[];cursor=0
        for second in range(math.ceil(start),math.ceil(end)):
            while cursor+1<len(frame_times) and frame_times[cursor+1]<=second:cursor+=1
            ft=frame_times[cursor] if frame_times else None
            visible=ft is not None and 0<=second-ft<=1 and ft not in unresolved_speed and approach.get('visibility_verified') is True
            queue_samples.append({'time':second,'length_m':queue_frames.get(ft,0),'visible':visible})
        signal_ok=scene.get('signal_synchronized') is True and approach.get('phase') is not None and not reset_within and coverage>=.8
        changes=[]
        for r in records:
            phase=r['payload'].get('phaseChange')
            if not phase:continue
            for p in phase.get('phases',[]):
                if str(p.get('phaseNumber'))==str(approach.get('phase')):
                    t=r['sensor_time']
                    if phase.get('absolute'):
                        try:
                            d=datetime.fromisoformat(p.get('timestamp','').replace('Z','+00:00'))
                            if d.tzinfo is None:raise ValueError()
                            t=d.timestamp()
                        except ValueError:signal_ok=False;continue
                    changes.append((t,int(p.get('status',0))))
        changes=sorted(set(changes));green_seconds=0;cycles=[]
        def green_at(t):
            values=[status for at,status in changes if at<=t]
            return None if not values or values[-1]==0 else values[-1]==1
        if not changes or green_at(start) is None:signal_ok=False
        for i,(t,status) in enumerate(changes):
            next_t=changes[i+1][0] if i+1<len(changes) else end
            if status==1:
                green_seconds+=max(0,min(end,next_t)-max(start,t))
                if start<=t<next_t<=end and i+1<len(changes):
                    nearest=[q for q in queue_samples if 0<=next_t-q['time']<=1 and q['visible']]
                    if nearest:cycles.append({'start':t,'end':next_t,'residual_queue_m':nearest[-1]['length_m'],'visible':True})
            if status==0 and max(t,start)<min(next_t,end):signal_ok=False
        for track in annotated:
            if signal_ok and track['arrival'] is not None:track['green']=green_at(track['arrival'])
            if signal_ok and track['exit'] is not None:track['departed_from_queue_on_green']=track['was_queued'] and green_at(track['exit']) is True
            del track['was_queued']
        visible_fraction=sum(q['visible'] for q in queue_samples)/len(queue_samples) if queue_samples else 0
        w={'site':site['id'],'approach':approach['id'],'source':'sdk-derived','start':start,'end':end,'length_m':length,'free_speed_mps':approach['free_speed_mps'],'lanes':approach['lanes'],'coverage':min(coverage,visible_fraction),'signal_synchronized':signal_ok,'entry_observation_complete':coverage>=.8 and approach.get('visibility_verified') is True,'departure_observation_complete':coverage>=.8 and signal_ok and approach.get('visibility_verified') is True,'green_seconds':green_seconds if signal_ok else None,'tracks':annotated,'queue_samples':queue_samples,'cycles':cycles,'provenance':{'calculation_version':VERSION,'calibration_version':site['calibration']['version'],'scene_version':scene['version'],'raw_event_keys':[r['event_key'] for r in records if start<=r['sensor_time']<end],'merge_count':0,'ambiguous_assignments':ambiguous,'collector_reset':reset_within,'speed_method':'position differences','stop_threshold_mps':threshold}}
        result=calculate(w);result['provenance']=w['provenance']
        if end-start>300:
            result['values']['discharge']=None
            result['quality']['flags'].append('Discharge rate is real-time only in the specification')
        if reset_within:result['quality']['flags'].append('Collector restart within reporting window')
        if ambiguous:result['quality']['flags'].append('Ambiguous lane assignments excluded')
        if result['quality']['flags']:result['quality']['status']='provisional'
        outputs.append((w,result))
    return outputs


def process_range(store,site,start,end,cadence='five_minute'):
    validate_scene(site)
    if end<=start:raise ValueError('End must follow start')
    if cadence not in ['five_minute','daily']:raise ValueError('Unknown cadence')
    if end-start>2*86400:raise ValueError('Process at most two days per request')
    records=[];cursor=0
    while True:
        page=store.raw_page(site=site['id'],start=start-300,end=end+300,after=cursor,limit=1000)
        records.extend(page['items'])
        if page['next_cursor'] is None:break
        cursor=page['next_cursor']
    windows=[]
    if cadence=='daily':
        local=datetime.fromtimestamp(start,ZoneInfo(site.get('timezone','America/Toronto')))
        a,b=calendar_bounds(local.date().isoformat(),site.get('timezone','America/Toronto'))
        if start!=a or end!=b:raise ValueError('Daily processing requires exactly one local calendar day')
        windows=[(start,end)]
    else:
        if start%300 or end%300:raise ValueError('Use five-minute-aligned UTC boundaries')
        windows=[(s,s+300) for s in range(int(start),int(end),300)]
    if not any(start<=r['sensor_time']<end and 'frame' in r['payload'] and r['status']=='received' for r in records):
        raise ValueError('No valid received frames in this interval')
    results=[]
    for a,b in windows:results.extend(build_window(site,records,a,b))
    store.save_windows(results)
    return {'saved':len(results),'source':'sdk-derived','calculation_version':VERSION}
