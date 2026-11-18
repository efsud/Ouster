"""Conservative CTM virtual tracers, not recovered individual vehicle identities.

LightSim equations 1--5; DeepCTM observed/virtual-cell distinction. No neural
checkpoint is fitted here. All geometry, lane count and boundary states are proxies.
"""
VEHICLES={str(i) for i in [1,2,3,4,5,6,7,8,9,15]}
DT=1.; JAM=.30; W=5.


def step(k, demand, downstream, dx, vf):
    """k veh/m over assumed two lanes; flow veh/s; CFL dt=1s."""
    capacity=vf*W*JAM/(vf+W)
    sending=[min(vf*v,capacity) for v in k]
    receiving=[min(capacity,W*(JAM-v)) for v in k]
    flow=[min(max(0,demand),receiving[0])]
    flow.extend(min(sending[i],receiving[i+1]) for i in range(len(k)-1))
    flow.append(min(sending[-1],max(0,W*(JAM-downstream)),capacity))
    new=[v+(flow[i]-flow[i+1])*DT/dx for i,v in enumerate(k)]
    error=abs(sum(new)*dx-sum(k)*dx-(flow[0]-flow[-1])*DT)
    speed=[min(vf,flow[i+1]/v) if v>1e-9 else vf for i,v in enumerate(k)]
    return new,speed,error


def features(site,direction):
    # Edie-style distance/time in the provisional 240m observation strip.
    distance=[0.]*60;duration=[0.]*60;counts=[set() for _ in range(60)]
    for j,tr in enumerate(site['tracks']):
        if tr['class_type'] not in VEHICLES or tr['direction']!=direction:continue
        for a,b in zip(tr['points'],tr['points'][1:]):
            dt=b[0]-a[0]
            if not 0<dt<=1.5:continue # never train boundary proxies on interpolated gaps
            lo=max(0,int(a[0]//60));hi=min(59,int(b[0]//60))
            for i in range(lo,hi+1):
                overlap=max(0,min(b[0],(i+1)*60)-max(a[0],i*60))
                distance[i]+=abs(b[1]-a[1])*overlap/dt;duration[i]+=overlap
                if overlap:counts[i].add(j)
    coverage=site.get('coverage', [0.]*60)
    return [dict(q=distance[i]/(240*60),k=duration[i]/(240*60),v=distance[i]/duration[i] if duration[i] else None,
                 valid=coverage[i]>=.8 and len(counts[i])>=3) for i in range(60)]


def estimate(snapshot):
    links=[]
    for a,b in zip(snapshot['sites'],snapshot['sites'][1:]):
        gap=b['station_m']-a['station_m']
        # Do not invent a blind segment if provisional observation strips overlap.
        if gap<245:continue
        length=gap-240;nc=max(1,int(length/30));dx=length/nc
        for direction in ['eastbound','westbound']:
            up,down=(a,b) if direction=='eastbound' else (b,a);sign=1 if direction=='eastbound' else -1
            fa,fb=features(up,direction),features(down,direction)
            # descriptive historical reconstruction uses this snapshot's observations,
            # not an evaluated forecast. Clamp vf to an explicit urban-road prior.
            values=[f['v'] for f in fa+fb if f['valid'] and f['v'] is not None]
            vf=max(8.,min(22.,sorted(values)[int(.85*(len(values)-1))])) if values else 13.89
            vf=min(vf,dx) # CFL even for very short remaining gaps
            field={};k=None;maximum_error=0.;valid_minutes=0
            for minute in range(60):
                left,right=fa[minute],fb[minute]
                if not(left['valid'] and right['valid']):k=None;continue
                valid_minutes+=1
                if k is None:k=[min(JAM,max(0,left['k']+(right['k']-left['k'])*(i+.5)/nc)) for i in range(nc)]
                for t in range(minute*60,(minute+1)*60):
                    k,speed,error=step(k,left['q'],min(JAM,right['k']),dx,vf)
                    maximum_error=max(maximum_error,error);field[t]=speed
            paths=[];origin=up['station_m']+sign*120;last_seed=-1e9
            # Start at observed strip crossings, without claiming a downstream match.
            seeds=[]
            for tr in up['tracks']:
                if tr['class_type'] not in VEHICLES or tr['direction']!=direction:continue
                pts=tr['points'];last=pts[-1]
                if abs(last[1]-origin)<=15:seeds.append(last)
            for seed in sorted(seeds):
                t=seed[0]
                if t-last_seed<15:continue # display thinning only, not predicted traffic counts
                last_seed=t;pos=sign*(seed[1]-origin);points=[list(seed)];stop='window_end'
                for _ in range(600):
                    speeds=field.get(int(t))
                    if speeds is None:stop='insufficient_boundary_data';break
                    cell=min(nc-1,max(0,int(max(0,pos)/dx)));v=speeds[cell]
                    delta=min(1.,3600-t)
                    if delta<=0:break
                    if v>0:delta=min(delta,(length-pos)/v)
                    if delta<=0:stop='downstream_observation_boundary';break
                    pos+=v*delta;t+=delta;points.append([round(t,2),round(origin+sign*pos,2),round(v,2)])
                    if pos>=length-1e-6:stop='downstream_observation_boundary';break
                else:stop='ten_minute_limit'
                if len(points)>=3:paths.append({'points':points,'termination':stop})
            links.append({'sites':[a['id'],b['id']],'direction':direction,'paths':paths,'valid_minutes':valid_minutes,
                          'cell_count':nc,'cell_length_m':dx,'free_speed_mps':vf,'max_mass_error_vehicles':maximum_error,
                          'method':'CTM virtual tracer (provisional, pooled vehicles)','state':'available' if paths else 'insufficient_supported_paths'})
    return {'method':'CTM reconstruction baseline; not trained DeepCTM','links':links,
            'assumptions':{'dt_s':DT,'jam_density_veh_m':JAM,'wave_speed_mps':W,'lanes':2,'coverage_min':.8,'minimum_tracks_per_minute':3},
            'limitations':['Representative motion, not cross-sensor identity matching.','No verified signal gates, lane geometry or lateral turning flows.','Uses contemporaneous boundary observations; not an out-of-sample forecast.','Unavailable boundary minutes stop paths. No pedestrian/cyclist model.','Boundary density/flow proxies omit rejected and stationary-only tracks.','Intermediate trajectory accuracy is unverified.']}


def gap_validation(snapshot):
    # Hide an interior point; compare endpoint interpolation with forward persistence.
    errors=[];baseline=[]
    for site in snapshot['sites']:
        for tr in site['tracks']:
            p=tr['points']
            for i in range(2,len(p)-1,13):
                before,a,target,b=p[i-2:i+2]
                dt=b[0]-a[0]
                if not .5<=dt<=3 or not 0<a[0]-before[0]<=1.5:continue
                ratio=(target[0]-a[0])/dt
                errors.append(abs(a[1]+ratio*(b[1]-a[1])-target[1]))
                baseline.append(abs(a[1]+(a[1]-before[1])/(a[0]-before[0])*(target[0]-a[0])-target[1]))
    return {'method':'Artificially masked interior points; local along-road position only, not cross-sensor validation',
            'count':len(errors),'interpolation_mae_m':sum(errors)/len(errors) if errors else None,
            'constant_velocity_mae_m':sum(baseline)/len(baseline) if baseline else None}
