"""Chronological speed-color matching. Estimates never alter observations."""
import math
from bisect import bisect_right
from collections import defaultdict
from .spatial_bridges import endpoint, reconstruct
from .local_gaps import VEHICLES

METHOD='color_slope_chronological_v1'

def color_band(speed):
    # Same continuous HSL palette as the renderer; match quantized 6-degree hues.
    return min(20, int(max(0, abs(speed))))

def bridge(a,b,max_gap=120,max_residual=20):
    if not all(math.isfinite(e[k]) for e in (a,b) for k in ('t','x','v')):return None
    dt=b['t']-a['t'];dx=b['x']-a['x'];v=a['v']
    if not 1.5<dt<=max_gap or color_band(a.get('color_speed',v))!=color_band(b.get('color_speed',b['v'])):return None
    if abs(v)>35 or abs(b['v'])>35 or v*b['v']<0 or abs(v-b['v'])>1:return None
    residual=dx-v*dt
    if abs(residual)>max_residual:return None
    # Keep the original slope for 80%; use the smallest endpoint correction
    # over the remaining 20%. Reject excessive speed changes or reversals.
    correction=residual/(.2*dt);tail=v+correction
    if abs(correction)>.5 or abs(tail)>35 or tail*v<0:return None
    if abs(v)<.5 and abs(dx)>.5:return None
    n=max(2,math.ceil(dt/.5));times=sorted(set([dt*i/n for i in range(n+1)]+[.8*dt]))
    points=[[a['t']+t,a['x']+v*t+correction*max(0,t-.8*dt),abs(v if t<.8*dt else tail)] for t in times]
    points[-1][1]=b['x']
    return dict(points=points,residual_m=residual,speed_adjustment_mps=correction,color_band_mps=color_band(a.get('color_speed',v)),constant_slope_mps=v)

def associate(left,right,max_gap=120,max_residual=20,max_distance=350,eligible=None):
    used=set();matches=[]
    ordered=sorted(enumerate(right),key=lambda z:z[1]['t']);times=[b['t'] for _,b in ordered]
    for i,a in sorted(enumerate(left),key=lambda z:(z[1]['t'],z[0])):
        options=[]
        for j,b in ordered[bisect_right(times,a['t']+1.5):bisect_right(times,a['t']+max_gap)]:
            if j in used or a.get('fragment')==b.get('fragment') and a.get('site')==b.get('site') and a.get('site') is not None:continue
            if a.get('direction')!=b.get('direction'):continue
            if abs(b['x']-a['x'])>max_distance:continue
            if a.get('session') and b.get('session') and a.get('site')==b.get('site') and a['session']!=b['session']:continue
            if eligible is not None and not eligible(a,b):continue
            p=bridge(a,b,max_gap,max_residual)
            if p:options.append((abs(p['residual_m']),b['t'],j,p))
        if not options:continue
        options.sort(key=lambda x:x[:3]);cost,_,j,p=options[0]
        # Equal geometric evidence does not identify a vehicle.
        margin=options[1][0]-cost if len(options)>1 else None
        if margin is not None and margin<.25:continue
        used.add(j);matches.append(dict(left=i,right=j,cost=cost,margin=margin,**p))
    return matches

def generate(snapshot):
    local=[]
    for site in snapshot['sites']:
        by_direction=defaultdict(list)
        for tr in site['tracks']:
            if tr.get('method') or tr['class_type'] not in VEHICLES:continue
            parts=[[]]
            for p in tr['points']:
                if parts[-1] and p[0]-parts[-1][-1][0]>1.5:parts.append([])
                parts[-1].append(p)
            for part in parts:
                by_direction[tr['direction']].append((tr,part))
        for direction,fragments in by_direction.items():
            ends=[];starts=[]
            for index,(tr,points) in enumerate(fragments):
                key=tr.get('source_key',[])
                for dest,is_exit in ((ends,True),(starts,False)):
                    e=endpoint(points,is_exit)
                    if e:dest.append(dict(e,fragment=index,site=site['id'],direction=direction,session=key[0] if key else None,identity=key[:2],class_type=tr['class_type']))
            for m in associate(ends,starts,max_gap=90,max_residual=10,max_distance=350):
                a,b=ends[m['left']],starts[m['right']]
                local.append(dict(site=site['id'],direction=direction,class_type=a['class_type'],method=METHOD,source='inferred',identity='same_sensor_session_id' if a['identity'] and a['identity']==b['identity'] else 'unverified_local_association',**{k:v for k,v in m.items() if k not in ('left','right')}))
    # Preserve existing corridor exit/entry and coverage-edge filtering.
    links=reconstruct(snapshot,matcher=lambda a,b:associate(a,b))['links'];between=[]
    for link in links:
        for p in link['paths']:
            between.append(dict(sites=link['sites'],direction=link['direction'],class_type=p['class_type'],points=p['points'],method=METHOD,source='inferred',identity='unverified_cross_sensor_association',association_cost=p['association_cost']))
    return dict(state='ready',method=METHOD,association_method=METHOD,within_intersection=local,between_intersections=between,
        generated_at=__import__('time').time(),snapshot_generated_at=snapshot['generated_at'],start=snapshot['start'],end=snapshot['end'],expires_at=snapshot['start']+5400,
        transform_manifest=snapshot.get('transform_manifest'),comparison={},uncertainty={'state':'experimental'},
        limitations=['Same 1 m/s color band, chronological minimum-distance matching; ties remain unresolved.',
        'Original slope retained for 80% of a gap; bounded endpoint correction over final 20%.',
        'Speed similarity does not verify identity. No observed points are modified.'])
