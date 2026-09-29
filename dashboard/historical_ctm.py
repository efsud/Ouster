"""Provisional single-approach CTM driven by assumed directional count-line crossings."""
import math
import json
from datetime import datetime
from .analytics import finite,percentile,METRICS

VERSION='historical-ctm-1'
VEHICLES={'1','2','3','4','5','6','7','8','9','15'}

def parameters(values):
    p={'axis':'x','line_m':0,'direction':1,'width_m':30,'length_m':300,'lanes':1,'free_speed_mps':13.89,'wave_speed_mps':5,'jam_veh_km_lane':150,'cycle_s':90,'green_s':45,'offset_s':0}
    p.update({k:v for k,v in values.items() if k in p})
    if p['axis'] not in ['x','y']:raise ValueError('Count-line axis must be x or y')
    for k,v in p.items():
        if k!='axis':finite(v,k)
    if p['direction'] not in [-1,1]:raise ValueError('Direction must be +1 or -1')
    if not 1<=p['lanes']<=6 or int(p['lanes'])!=p['lanes']:raise ValueError('Use 1–6 lanes')
    if not 50<=p['length_m']<=1000 or not 1<=p['width_m']<=200:raise ValueError('Length 50–1000 m; count-line width 1–200 m')
    if not 1<=p['free_speed_mps']<=35 or not 1<=p['wave_speed_mps']<=15:raise ValueError('Unsupported speed parameters')
    if not 50<=p['jam_veh_km_lane']<=250 or not 10<=p['cycle_s']<=180 or not 0<=p['green_s']<=p['cycle_s']:raise ValueError('Invalid density or signal assumptions')
    return p

def inputs(records,start,end,p):
    bins=[{'start':start+i*300,'end':min(end,start+(i+1)*300),'crossings':0,'covered_s':0,'frames':0} for i in range(math.ceil((end-start)/300))]
    previous={};counted=set();last_frame=None;events=0
    def clock(event):
        stamp=event.get('frame',{}).get('timestamp') or event.get('timestamp')
        try:return datetime.fromisoformat(stamp.replace('Z','+00:00'))
        except (ValueError,TypeError,AttributeError):return None
    for r in records:
        t=r['received_at'];event=r['payload']
        if not start<=t<end or 'frame' not in event:continue
        if r['status']!='received' and r.get('reason')!='unknown_timezone':continue
        i=min(len(bins)-1,int((t-start)//300));bins[i]['frames']+=1;events+=1
        if last_frame is not None and 0<t-last_frame<=3:
            for j in range(max(0,int((last_frame-start)//300)),i+1):
                bins[j]['covered_s']+=max(0,min(t,bins[j]['end'])-max(last_frame,bins[j]['start']))
        last_frame=t;sensor_clock=clock(event)
        for o in event['frame'].get('objects',[]):
            if not isinstance(o,dict) or str(o.get('classType')) not in VEHICLES or not o.get('id'):continue
            try:x=finite(o.get('centerX'),'x');y=finite(o.get('centerY'),'y')
            except ValueError:continue
            if math.hypot(x,y)>5000:continue
            ident=(r['session'],str(o['id']));point=(x,y) if p['axis']=='x' else (y,x)
            prev=previous.get(ident);previous[ident]=(point,sensor_clock)
            if not prev or ident in counted or sensor_clock is None or prev[1] is None:continue
            try:dt=(sensor_clock-prev[1]).total_seconds()
            except TypeError:continue
            if not 0<dt<=3 or math.dist(prev[0],point)/dt>60:continue
            a=(prev[0][0]-p['line_m'])*p['direction'];b=(point[0]-p['line_m'])*p['direction']
            if a<0<=b:
                cross=prev[0][1]+(-a/(b-a))*(point[1]-prev[0][1])
                if abs(cross)<=p['width_m']/2:bins[i]['crossings']+=1;counted.add(ident)
    for b in bins:b['coverage']=min(1,b['covered_s']/(b['end']-b['start']))
    return bins,events

def model(bins,p):
    lanes=p['lanes'];v=p['free_speed_mps'];w=p['wave_speed_mps'];jam=p['jam_veh_km_lane']/1000*lanes
    cells=max(1,int(p['length_m']//50));dx=p['length_m']/cells;capacity=v*w*jam/(v+w)
    n=[0.]*cells;backlog=0.;rows=[];total_in=total_out=0.;segment_in=segment_out=0.;reset=True;origin=bins[0]['start'];max_error=0.
    for b in bins:
        values={k:None for k in METRICS};duration=b['end']-b['start']
        if b['coverage']<.8:
            rows.append(dict(b,values=values,flags=['Insufficient receipt coverage; model state reset before next valid interval']))
            n=[0.]*cells;backlog=0.;segment_in=segment_out=0.;reset=True;continue
        flags=['Provisional count-line geometry and signal assumptions','Receipt-time windows; sensor timezone unverified']
        if reset:flags.append('Empty initial model state / warm-up');reset=False
        rate=b['crossings']/duration;entered=departed=excess=green_time=cycles=failed=0.;queues=[];t=b['start']
        while t<b['end']-1e-8:
            dt=min(1.,b['end']-t)
            # dx >= max(v,w)*dt; triangular fundamental diagram, one approach.
            phase=(t-origin-p['offset_s'])%p['cycle_s'];green=phase<p['green_s']
            send=[min(v*a/dx,capacity)*dt for a in n]
            receive=[min(capacity,w*max(0,jam-a/dx))*dt for a in n]
            backlog+=rate*dt;entry=min(backlog,receive[0]);backlog-=entry
            flows=[entry]+[min(send[j],receive[j+1]) for j in range(cells-1)]+[send[-1] if green else 0]
            excess+=sum(max(0,n[j]*dt-flows[j+1]*dx/v) for j in range(cells))
            n=[max(0,n[j]+flows[j]-flows[j+1]) for j in range(cells)]
            entered+=entry;departed+=flows[-1];green_time+=dt if green else 0
            tail=0.
            for a in reversed(n):
                if a/dx>capacity/v:tail+=dx
                else:break
            queues.append(tail)
            if green and phase+dt>=p['green_s'] and 0<p['green_s']<p['cycle_s']:
                cycles+=1;failed+=tail>0
            t+=dt
        segment_in+=entered;segment_out+=departed;total_in+=entered;total_out+=departed
        error=segment_in-segment_out-sum(n);max_error=max(max_error,abs(error))
        values.update(control_delay=excess/departed if departed else None,queue_p95=percentile(queues,.95),volume=entered*3600/duration,discharge=departed*3600/green_time/lanes if green_time else None,split_failure=100*failed/cycles if cycles else None)
        rows.append(dict(b,values=values,flags=flags,model_entered=entered,model_departed=departed,upstream_backlog=backlog,conservation_error=error))
    return rows,max_error

LABELS={'control_delay':'CTM excess-time proxy','stopped_delay':'Stopped delay — unavailable from aggregate CTM','queue_p95':'CTM congested queue P95','aog':'AOG — unavailable without arrival/phase observations','split_failure':'CTM residual-queue cycle percentage','volume':'CTM admitted approach flow','discharge':'CTM outflow per green-hour/lane'}

def analyze(store,site,start,end,assumptions):
    finite(start,'start');finite(end,'end')
    if not 0<end-start<=3600.01:raise ValueError('Select a recorded range of at most one hour')
    p=parameters(assumptions)
    def records():
        with store.connect() as db:
            for r in db.execute('SELECT session,received_at,status,reason,payload FROM raw_events INDEXED BY raw_site_receipt WHERE site=? AND received_at>=? AND received_at<? ORDER BY received_at,sequence',(site,start,end)):
                yield {**dict(r),'payload':json.loads(r['payload'])}
    bins,count=inputs(records(),start,end,p)
    if not count:raise ValueError('No recorded frames in the selected receipt-time range')
    rows,error=model(bins,p)
    return {'site':site,'start':start,'end':end,'source':'provisional-recording-driven-ctm','version':VERSION,'assumptions':p,'input_frames':count,'crossings':sum(b['crossings'] for b in bins),'rows':rows,'max_conservation_error':error,'labels':LABELS,
        'limitations':['Count line and road/signal settings are user assumptions, not calibrated scene metadata.','Demand is measured directional crossings at the assumed line, held constant within each five-minute interval.','Sensor-local coordinates are used; map display rotation does not change this count line.','Receipt time is used for reporting; network buffering may shift counts in time.','Unknown clock offsets are accepted only for this provisional model; relative track gaps above 3 seconds are excluded.','Stopped delay and AOG require individual trajectories/validated signal events and are not produced by this CTM.','Excess time per departure is a macroscopic proxy, not the paper’s observed mean control delay.','Flow and green-hour discharge are CTM flow estimates, not validated physical trajectory counts.','The model is a single assumed approach with no turns or cross-sensor matching.','A queue P95 is derived from whole congested cells; resolution is approximately 50 metres.']}
