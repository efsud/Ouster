"""Receipt-aligned Edie features from original SDK trajectories; no zero-filled outages."""
import gzip
import json
import math
from datetime import datetime
from pathlib import Path
import numpy as np
from dashboard.historical_ctm import VEHICLES


def events(directory,site):
    # One worker per site. Hour + session filenames need an explicit receipt merge
    # after a reconnect (session IDs are random, not chronological).
    import heapq
    def read(path):
        with gzip.open(path,'rt') as f:
            for line in f:yield json.loads(line)
    return heapq.merge(*(read(p) for p in sorted(Path(directory).glob(site+'-*.jsonl.gz'))),key=lambda r:r['received_at'])


def clip_segment(a,b,length,width):
    lo=0.;hi=1.
    for axis,minimum,maximum in [(0,-length/2,length/2),(1,-width,width)]:
        delta=b[axis]-a[axis]
        if abs(delta)<1e-12:
            if not minimum<=a[axis]<=maximum:return None
        else:
            u=(minimum-a[axis])/delta;v=(maximum-a[axis])/delta
            lo=max(lo,min(u,v));hi=min(hi,max(u,v))
    return (lo,hi) if hi>lo else None


def extract_site(records,start,end,rotation,config):
    step=config['interval_s'];count=int((end-start)//step)
    # per direction: integrated vehicle-seconds and longitudinal vehicle-metres.
    duration=np.zeros((count,2));distance=np.zeros((count,2));coverage=np.zeros(count)
    frames=np.zeros(count,dtype=int);previous={};last=None;rejected=0
    angle=math.radians(rotation-config['road_bearing_east_deg']);co=math.cos(angle);si=math.sin(angle)
    def distribute(left,right,callback):
        if right<=left:return
        for k in range(max(0,int((left-start)//step)),min(count-1,int((right-start)//step))+1):
            span=max(0,min(right,start+(k+1)*step)-max(left,start+k*step))
            if span:callback(k,span)
    for record in records:
        receipt=record['received_at'];event=record['payload'];frame=event.get('frame')
        if not start<=receipt<start+count*step or frame is None:continue
        frames[int((receipt-start)//step)]+=1
        stamp=frame.get('timestamp') or event.get('timestamp')
        try:clock=datetime.fromisoformat(stamp.replace('Z','+00:00'))
        except (TypeError,ValueError,AttributeError):rejected+=1;continue
        session=record['session']
        if last and last[2]==session:
            try:ds=(clock-last[1]).total_seconds()
            except TypeError:ds=-1
            dr=receipt-last[0]
            # Reject receipt bursts and clock discontinuities, not just wall-clock gaps.
            if 0<ds<=3 and 0<dr<=3 and .5<=ds/dr<=2:
                distribute(last[0],receipt,lambda k,span:coverage.__setitem__(k,coverage[k]+span))
        last=(receipt,clock,session)
        for obj in frame.get('objects',[]):
            if str(obj.get('classType')) not in VEHICLES or 'id' not in obj:continue
            try:
                x=float(obj['centerX']);y=float(obj['centerY'])
                if not math.isfinite(x+y) or math.hypot(x,y)>500:continue
            except (KeyError,TypeError,ValueError):continue
            point=(co*x-si*y,si*x+co*y);key=(session,str(obj['id']));old=previous.get(key)
            previous[key]=(point,clock,receipt,old[3] if old else None)
            if not old:continue
            try:dt=(clock-old[1]).total_seconds()
            except TypeError:continue
            dr=receipt-old[2]
            if not (0<dt<=3 and 0<dr<=3 and .5<=dt/dr<=2):
                previous[key]=(point,clock,receipt,None);continue
            dx=point[0]-old[0][0];dy=point[1]-old[0][1]
            if math.hypot(dx,dy)/dt>60:
                previous[key]=(point,clock,receipt,None);continue
            direction=0 if dx>0 else 1
            if abs(dx)/dt<.3:
                if old[3] is None:continue
                direction=old[3]
            elif abs(dy)>abs(dx):
                previous[key]=(point,clock,receipt,None);continue # excludes predominantly cross-street movement
            previous[key]=(point,clock,receipt,direction)
            clip=clip_segment(old[0],point,config['roi_length_m'],config['roi_half_width_m'])
            if clip is None:continue
            a,b=clip
            # Receipt bins, relative sensor dt; bounded ratio above remains provisional.
            def add(k,span):
                fraction=span/dr
                duration[k,direction]+=dt*fraction
                distance[k,direction]+=abs(dx)*fraction
            distribute(old[2]+a*dr,old[2]+b*dr,add)
        # Bound memory and prevent stale/reused IDs from contributing across gaps.
        if len(previous)>10000:previous={k:v for k,v in previous.items() if receipt-v[2]<=3}
    length=config['roi_length_m']/1000
    density=duration/(length*step)
    flow=distance/1000/(length*step)*3600
    speed=np.divide(distance/1000,duration/3600,out=np.zeros_like(distance),where=duration>0)
    valid=(coverage[:,None]/step>=config['minimum_coverage']) & (duration>0)
    return np.stack([flow,density,speed],-1),valid,{'frames':frames.tolist(),'coverage':(coverage/step).tolist(),'invalid_clock_frames':rejected,'unclassified_stopped_tracks_excluded':True}


def prepare(directory,config,start,end):
    all_features=[];all_valid=[];quality=[]
    for i,site in enumerate(config['sites_west_to_east']):
        features,valid,evidence=extract_site(events(directory,site),start,end,config['rotation_deg'][i],config)
        all_features.append(features);all_valid.append(valid);quality.append(evidence)
    datasets={};n=len(config['cell_lengths_km']);t=len(all_features[0])
    for d,name in enumerate(['eastbound','westbound']):
        x=np.zeros((t,n,3),dtype=np.float32);mask=np.zeros((t,n),dtype=bool)
        for j,index in enumerate([0,1] if d==0 else [1,0]):
            node=config['observed_nodes'][j];x[:,node]=all_features[index][:,d];mask[:,node]=all_valid[index][:,d]
        datasets[name]=(x,mask)
    return datasets,quality


def split_sequences(x,mask,context,horizon):
    """Chronological 60/20/20 partitions, windows cannot cross partition or gap."""
    n=len(x);cuts=[0,int(n*.6),int(n*.8),n];result={}
    for label,left,right in zip(['train','validation','test'],cuts,cuts[1:]):
        samples=[]
        for i in range(left+context,right-horizon+1):
            # Endpoints required in every input and target bin; virtual cells remain masked.
            if mask[i-context:i+horizon][:,[0,-1]].all():samples.append(i)
        result[label]=samples
    return result
