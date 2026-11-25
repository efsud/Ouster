"""Display continuity for the same sensor/session/object, never cross-site identity.

The original constrained model keeps priority. This fallback interpolates only
between observed endpoints. Timing conflicts remain visible as gray connectors,
not speed estimates, and no connector is an observed sample or a KPI input.
"""
from collections import Counter, defaultdict
from datetime import datetime
import math
from statistics import median

from .local_gaps import VEHICLES

METHOD = 'same_id_monotone_continuity_v1'


def velocity(points, end):
    flank = points[-6:] if end else points[:6]
    slopes = [(b[1]-a[1])/(b[0]-a[0]) for a,b in zip(flank,flank[1:])
              if 0 < b[0]-a[0] <= 1.5]
    return median(slopes) if slopes else None


def curve(a, b, v0, v1, vmax=35.):
    """Monotone cubic, exact endpoints, bounded speed/acceleration within gap.

Limit noisy endpoint tangents rather than discarding an otherwise feasible ID
connection. Blending toward a secant is explicit, not an edit to observations.
"""
    dt=b[0]-a[0]; dx=b[1]-a[1]; sign=1 if dx>=0 else -1
    mean=abs(dx)/dt
    if mean>vmax:return None
    slopes=[mean if v is None else max(0.,v*sign) for v in (v0,v1)]
    if mean<1e-9:slopes=[0.,0.]
    else:
        norm=math.hypot(*(v/mean for v in slopes))
        if norm>3:slopes=[v*3/norm for v in slopes]
    original=list(slopes)
    for blend in (1.,.75,.5,.25,0.):
        u,v=[mean+blend*(s-mean) for s in original]
        # Speed is quadratic; extrema are at endpoints or its vertex.
        aa=3*(u+v-2*mean); bb=6*mean-4*u-2*v
        speeds=[u,v]
        if abs(aa)>1e-12 and 0 < -bb/(2*aa) < 1:
            z=-bb/(2*aa);speeds.append(aa*z*z+bb*z+u)
        if max(speeds)<=vmax+1e-8 and min(speeds)>=-1e-8 and max(abs(bb/dt),abs((2*aa+bb)/dt))<=4.+1e-8:
            break
    n=max(2,math.ceil(dt*2));out=[]
    for i in range(n+1):
        z=i/n
        distance=dt*((u+v-2*mean)*z**3+(3*mean-2*u-v)*z*z+u*z)
        speed=max(0.,aa*z*z+bb*z+u)
        out.append([a[0]+z*dt,a[1]+sign*distance,speed])
    out[0][:2]=list(a[:2]);out[-1][:2]=list(b[:2])
    return out,[sign*u,sign*v]


def connect(before, after, internal=False):
    a=before['points'][-1];b=after['points'][0];dt=b[0]-a[0]
    if not all(math.isfinite(float(v)) for v in (*a[:2],*b[:2])):return None,'invalid_coordinates'
    if dt<=.1:return None,'overlap_or_no_visible_gap'
    if dt>600:return None,'over_ten_minutes_identity_review_required'
    warnings=[];v0=velocity(before['points'],True);v1=velocity(after['points'],False)
    if v0 is None or v1 is None:warnings.append('limited_endpoint_context')
    dx=b[1]-a[1];direction=before.get('direction');sign=1 if direction=='eastbound' else -1
    quiet=abs(dx)<=3 and max(abs(v0 or 0),abs(v1 or 0))<=1
    if direction!=after.get('direction'):
        if not quiet:return None,'conflicting_travel_directions'
        warnings.append('stationary_direction_noise')
    if dx*sign < -3:return None,'reverse_motion_identity_review_required'
    if dx*sign < 0:warnings.append('small_position_reversal')
    try:
        sensor_dt=(datetime.fromisoformat(after['sensor_start'])-datetime.fromisoformat(before['sensor_end'])).total_seconds()
    except (KeyError,TypeError,ValueError):sensor_dt=None
    if sensor_dt is not None and sensor_dt<=0:return None,'sensor_clock_reset_or_reordered_identity'
    uncertain=internal or sensor_dt is None or not .8<=sensor_dt/dt<=1.2
    if uncertain:warnings.append('timing_unverified' if sensor_dt is None or internal else 'sensor_display_timing_disagreement')
    lateral=None
    if 'lateral_start_m' in after and 'lateral_end_m' in before:
        lateral=abs(after['lateral_start_m']-before['lateral_end_m'])
        if math.hypot(dx,lateral)/dt>35:return None,'impossible_average_displacement'
        if lateral>2:warnings.append('lateral_motion')
    if dt>30:warnings.append('long_gap_motion_unobserved')
    result=curve(a,b,v0,v1)
    if result is None:return None,'impossible_average_displacement'
    points,tangents=result
    if any(v is not None and abs(v-t)>1 for v,t in zip((v0,v1),tangents)):
        warnings.append('endpoint_tangents_limited')
    key=list(before['source_key'][:2])
    return dict(identity_key=key,object_id=key[1],direction=direction,
        endpoint_directions=[direction,after.get('direction')],class_type=before['class_type'],
        endpoint_classes=[before['class_type'],after['class_type']],classification_changed=before['class_type']!=after['class_type'],
        points=points,source='inferred',method=METHOD,identity='same_sensor_session_object_continuity',
        gap_kind='internal_sampling_gap' if internal else 'same_id_fragment_break',gap_s=dt,
        exact_endpoint_interpolation=True,kpi_eligible=False,timing_uncertain=uncertain,
        speed_available=not uncertain,speed_basis='interpolated_position_derivative_on_display_time',
        sensor_elapsed_s=sensor_dt,lateral_displacement_m=lateral,warnings=warnings,
        observed_endpoint_slopes=[v0,v1],interpolated_endpoint_slopes=tangents),None


def pairs(site):
    groups=defaultdict(list)
    for tr in site['tracks']:
        key=tr.get('source_key',[])
        if tr.get('method') or len(key)<2 or not all(key[:2]) or not tr.get('points'):continue
        groups[tuple(key[:2])].append(tr)
        if tr.get('class_type') not in VEHICLES:continue
        for i,(a,b) in enumerate(zip(tr['points'],tr['points'][1:]),1):
            if b[0]-a[0]>1.5:
                yield dict(tr,points=tr['points'][:i],sensor_end=None),dict(tr,points=tr['points'][i:],sensor_start=None),True
    for tracks in groups.values():
        tracks.sort(key=lambda tr:tr['points'][0][0])
        before=tracks[0]
        for after in tracks[1:]:
            if after['points'][0][0]-before['points'][-1][0]<=.1:
                # A nested/overlapping classification fragment must not make us
                # draw an estimate over positions already observed by this ID.
                if after['points'][-1][0]>before['points'][-1][0]:before=after
                continue
            if before.get('class_type') in VEHICLES or after.get('class_type') in VEHICLES:
                yield before,after,False
            before=after


def token(site,key,a,b):
    return site,tuple(key),round(a[0],3),round(b[0],3)


def extend(snapshot, local):
    existing={token(p['site'],p['identity_key'],p['points'][0],p['points'][-1]) for p in local if p.get('identity_key')}
    additions=[];sites=[]
    for site in snapshot['sites']:
        counts=Counter();rejected=Counter();warnings=Counter()
        for before,after,internal in pairs(site):
            counts['same_id_gaps']+=1
            key=token(site['id'],before['source_key'][:2],before['points'][-1],after['points'][0])
            if key in existing:counts['previously_connected']+=1;continue
            path,reason=connect(before,after,internal)
            if path is None:rejected[reason]+=1;continue
            path['site']=site['id'];additions.append(path);existing.add(key)
            counts['added']+=1;counts['timing_uncertain']+=path['timing_uncertain'];warnings.update(path['warnings'])
        sites.append(dict(site=site['id'],name=site['name'],**counts,unresolved=sum(rejected.values()),reasons=dict(rejected),warnings=dict(warnings)))
    return local+additions,dict(method=METHOD,sites=sites,added=len(additions),
        timing_uncertain=sum(p['timing_uncertain'] for p in additions),
        unresolved=sum(s['unresolved'] for s in sites),kpi_eligible=False,
        note='Same sensor/session/ID; classification-independent. Dashed interpolation is not observed motion. Gray means timing is uncertain and no speed is reported.')


def apply(snapshot,layers):
    """Versioned derived layer; leaves the frozen observations/base output intact."""
    local,review=extend(snapshot,layers.get('within_intersection',[]))
    result=dict(layers,within_intersection=local,same_id_continuity=review)
    # An internal same-ID fragment endpoint cannot simultaneously be a corridor
    # departure/arrival. Suppress only exact provenance matches, never rematch.
    blocked=set()
    for p in local:
        if p.get('method')!=METHOD:continue
        for role,point in (('departure',p['points'][0]),('arrival',p['points'][-1])):
            blocked.add((p['site'],tuple(p['identity_key']),role,round(point[0],3),round(point[1],3)))
    def conflict(p):
        for role,ref in p.get('endpoint_provenance',{}).items():
            if not isinstance(ref,dict) or not ref.get('observed_endpoint'):continue
            point=ref['observed_endpoint']
            if (ref['site'],tuple(ref['source_key'][:2]),role,round(point[0],3),round(point[1],3)) in blocked:return True
        return False
    result['between_intersections']=[p for p in layers.get('between_intersections',[]) if not conflict(p)]
    # Avoid drawing an old experimental proposal over the new same-ID bridge.
    if layers.get('residual_color'):
        keys={token(p['site'],p['identity_key'],p['points'][0],p['points'][-1]) for p in local if p.get('identity_key')}
        result['residual_color']=dict(layers['residual_color'])
        result['residual_color']['within_intersection']=[p for p in layers['residual_color'].get('within_intersection',[])
            if not p.get('identity_key') or token(p['site'],p['identity_key'],p['points'][0],p['points'][-1]) not in keys]
        result['residual_color']['between_intersections']=[p for p in layers['residual_color'].get('between_intersections',[]) if not conflict(p)]
    review['superseded_between_links']=len(layers.get('between_intersections',[]))-len(result['between_intersections'])
    from .coverage_audit import audit
    result['coverage_audit']=audit(snapshot,result)
    return result
