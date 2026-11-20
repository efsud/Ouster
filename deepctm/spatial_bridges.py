"""Experimental spatial blind-band reconstruction, distinct from local time gaps.

Endpoint-constrained monotone cubic paths and conservative fragment association.
An association is a hypothesis, never a verified cross-sensor vehicle identity.
"""
import math
from statistics import median
from .local_gaps import VEHICLES

def endpoint(points,exit_side):
    p=points[-5:] if exit_side else points[:5]
    if len(p)<5 or p[-1][0]-p[0][0]<1:return None
    slopes=[]
    for a,b in zip(p,p[1:]):
        dt=b[0]-a[0]
        if not 0<dt<=1.5:return None
        slopes.append((b[1]-a[1])/dt)
    return {'t':p[-1][0] if exit_side else p[0][0],'x':p[-1][1] if exit_side else p[0][1],'v':median(slopes)}

def queue_curve(a,b,step=.25):
    """Candidate brake--wait--accelerate path; assumed 3 m/s², stop near entry.

    Endpoint-only retrospective hypothesis. Returns None if its assumed stop is
    incompatible with available distance or time; never implies observed red.
    """
    duration=b['t']-a['t'];distance=abs(b['x']-a['x']);sign=1 if b['x']>a['x'] else -1
    v0=max(0,a['v']*sign);v1=max(0,b['v']*sign);acc=3.
    if min(v0,v1)<1 or max(v0,v1)>35 or duration<=0:return None
    brake=v0/acc;accelerate=v1/acc;d0=v0*brake/2;d1=v1*accelerate/2
    extra=distance-d0-d1
    if extra<0:return None
    cruise=extra/v1;wait=duration-brake-accelerate-cruise
    if wait<2:return None
    result=[];n=max(2,math.ceil(duration/step))
    for i in range(n+1):
        t=duration*i/n
        if t<brake:x=v0*t-.5*acc*t*t;v=v0-acc*t
        elif t<brake+wait:x=d0;v=0.
        elif t<brake+wait+accelerate:
            u=t-brake-wait;x=d0+.5*acc*u*u;v=acc*u
        else:x=d0+d1+v1*(t-brake-wait-accelerate);v=v1
        result.append([a['t']+t,a['x']+sign*x,v])
    return result

def curve(a,b,method='monotone',step=.25):
    if method not in {'linear','hermite','monotone','queue'}:raise ValueError('Unknown spatial reconstruction method')
    if not all(math.isfinite(float(e[k])) for e in (a,b) for k in ('t','x','v')):return None
    dt=b['t']-a['t'];dx=b['x']-a['x']
    if not 0<dt<=120 or abs(dx)<2:return None
    secant=dx/dt;sign=1 if dx>0 else -1
    if abs(secant)>35 or a['v']*sign<-.5 or b['v']*sign<-.5:return None
    if method=='queue':
        queued=queue_curve(a,b,step)
        if queued is not None:return queued
        method='monotone'
    va=max(0,a['v']*sign)*sign;vb=max(0,b['v']*sign)*sign
    if method=='linear':va=vb=secant
    elif method=='monotone':
        alpha=va/secant;beta=vb/secant;norm=math.hypot(alpha,beta)
        if norm>3:va*=3/norm;vb*=3/norm
    result=[];steps=max(2,math.ceil(dt/step))
    for i in range(steps+1):
        u=i/steps;m=va*dt;n=vb*dt
        x=(2*u**3-3*u*u+1)*a['x']+(u**3-2*u*u+u)*m+(-2*u**3+3*u*u)*b['x']+(u**3-u*u)*n
        v=((6*u*u-6*u)*a['x']+(3*u*u-4*u+1)*m+(-6*u*u+6*u)*b['x']+(3*u*u-2*u)*n)/dt
        acc=((12*u-6)*a['x']+(6*u-4)*m+(-12*u+6)*b['x']+(6*u-2)*n)/dt**2
        if method!='linear' and (v*sign<-.1 or abs(v)>35 or abs(acc)>4):return None
        result.append([a['t']+u*dt,x,abs(v)])
    return result

def pair_cost(a,b):
    dt=b['t']-a['t'];dx=b['x']-a['x'];sign=1 if dx>0 else -1
    if not 0<dt<=120 or not 2<abs(dx)<350 or min(a['v']*sign,b['v']*sign)<1:return None
    speed=(abs(a['v'])+abs(b['v']))/2;expected=abs(dx)/speed
    if abs(dx)/dt>35:return None
    return abs(dt-expected)/max(2,.35*expected)+abs(abs(a['v'])-abs(b['v']))/15+(0 if a['class_type']==b['class_type'] else .75)

def associate(left,right,threshold=1.5,margin=.25,method="legacy"):
    if method=="augmented":
        baseline=associate(left,right,threshold,margin,method="legacy")
        used_a={m['left'] for m in baseline};used_b={m['right'] for m in baseline}
        # Keep competitors visible even when occupied: avoid a cascade of false
        # certainty caused by treating earlier identity hypotheses as ground truth.
        proposed=associate_residual(left,right,threshold,margin,max_rounds=1)
        extra=[m for m in proposed if m['left'] not in used_a and m['right'] not in used_b and m['cost']<=.15 and m['margin']>=.5]
        for m in extra:m['assignment_round']=1;m['additional']=True
        return baseline+extra
    if method=="residual":return associate_residual(left,right,threshold,margin)
    if method!="legacy":raise ValueError("Unknown association method")
    candidates=[];by_left={};by_right={}
    for i,a in enumerate(left):
        for j,b in enumerate(right):
            if b['t']<=a['t'] or b['t']>a['t']+120:continue
            cost=pair_cost(a,b)
            if cost is None or cost>threshold:continue
            candidates.append((cost,i,j));by_left.setdefault(i,[]).append(cost);by_right.setdefault(j,[]).append(cost)
    used_a=set();used_b=set();accepted=[]
    for cost,i,j in sorted(candidates):
        if i in used_a or j in used_b:continue
        # Require separation from competing associations on both sides.
        alt_a=sorted(by_left[i]);alt_b=sorted(by_right[j])
        separation=min(alt_a[1]-cost if len(alt_a)>1 else 99,alt_b[1]-cost if len(alt_b)>1 else 99)
        if separation<margin:continue
        points=curve(left[i],right[j])
        if points is None:continue
        used_a.add(i);used_b.add(j);accepted.append({'left':i,'right':j,'cost':cost,'margin':separation,'points':points})
    return accepted

def associate_residual(left,right,threshold=1.5,margin=.25,max_rounds=None):
    """Resolve mutual-best matches in rounds; remove occupied endpoints from rivals.

    Infeasible curves cannot compete. Never relax cost/margin gates, reuse an
    endpoint, or break ties merely to increase coverage. Round > 1 is conditional
    on earlier hypotheses, not independent additional identity evidence.
    """
    candidates={}
    for i,a in enumerate(left):
        for j,b in enumerate(right):
            cost=pair_cost(a,b)
            if cost is None or cost>threshold:continue
            points=curve(a,b)
            if points is not None:candidates[i,j]=(cost,points)
    accepted=[];round_number=0
    while candidates and (max_rounds is None or round_number<max_rounds):
        round_number+=1;by_a={};by_b={}
        for (i,j),(cost,points) in candidates.items():
            by_a.setdefault(i,[]).append((cost,j));by_b.setdefault(j,[]).append((cost,i))
        for group in (*by_a.values(),*by_b.values()):group.sort()
        selected=[]
        for i,options in by_a.items():
            cost,j=options[0];reverse=by_b[j]
            if reverse[0][1]!=i:continue
            separation=min(options[1][0]-cost if len(options)>1 else 99,reverse[1][0]-cost if len(reverse)>1 else 99)
            if separation<margin:continue
            selected.append((i,j));accepted.append(dict(left=i,right=j,cost=cost,margin=separation,points=candidates[i,j][1],assignment_round=round_number))
        if not selected:break
        used_a={i for i,j in selected};used_b={j for i,j in selected}
        candidates={k:v for k,v in candidates.items() if k[0] not in used_a and k[1] not in used_b}
    return accepted

def reconstruct(snapshot,association_method="augmented"):
    from statistics import quantiles
    links=[]
    for west,east in zip(snapshot['sites'],snapshot['sites'][1:]):
        for direction in ['eastbound','westbound']:
            sign=1 if direction=='eastbound' else -1;up,down=(west,east) if sign==1 else (east,west)
            groups=[];diagnostics=[]
            for site,is_exit in [(up,True),(down,False)]:
                group=[];counts=dict(vehicle_fragments=0,movement_rejected=0,endpoint_rejected=0)
                for index,tr in enumerate(site['tracks']):
                    if tr['direction']!=direction or tr['class_type'] not in VEHICLES:continue
                    counts['vehicle_fragments']+=1
                    movement=tr.get('movement',{})
                    if site.get('movement_summary') is not None:
                        # Leaving SR-436 ends a corridor path; joining starts one.
                        flag='can_match_next' if is_exit else 'can_match_previous'
                        route_direction='outgoing_direction' if is_exit else 'incoming_direction'
                        if not movement.get(flag) or movement.get(route_direction)!=direction:
                            counts['movement_rejected']+=1;continue
                    ep=endpoint(tr['points'],is_exit)
                    if ep and ep['v']*sign>=1:group.append(dict(ep,class_type=tr['class_type'],fragment=index,movement=movement))
                    else:counts['endpoint_rejected']+=1
                diagnostics.append(counts);groups.append(group)
            left,right=groups
            if len(left)<10 or len(right)<10:
                links.append(dict(sites=[up['id'],down['id']],names=[up['name'],down['name']],direction=direction,departure_candidates=len(left),arrival_candidates=len(right),diagnostics=diagnostics,paths=[],reason='Insufficient endpoints for coverage-edge estimation'));continue
            out=quantiles([e['x']*sign for e in left],n=10)[-1];entry=quantiles([e['x']*sign for e in right],n=10)[0]
            # Actual fragment ends near each site's outer coverage edge, not station centers.
            before_edge=[len(left),len(right)]
            left=[e for e in left if abs(e['x']*sign-out)<=30];right=[e for e in right if abs(e['x']*sign-entry)<=30]
            for counts,before,after in zip(diagnostics,before_edge,[len(left),len(right)]):counts['away_from_coverage_edge']=before-after
            matches=associate(left,right,method=association_method)
            paths=[{'points':m['points'],'class_type':left[m['left']]['class_type'],'direction':direction,'association_cost':m['cost'],'ambiguity_margin':m['margin'],'assignment_round':m.get('assignment_round',1),'additional':m.get('additional',False),'upstream_movement':left[m['left']].get('movement',{}),'downstream_movement':right[m['right']].get('movement',{}),'upstream_fragment':left[m['left']]['fragment'],'downstream_fragment':right[m['right']]['fragment']} for m in matches]
            links.append({'sites':[up['id'],down['id']],'names':[up['name'],down['name']],'direction':direction,'departure_candidates':len(left),'arrival_candidates':len(right),'diagnostics':diagnostics,'unmatched_departures':len(left)-len(paths),'unmatched_arrivals':len(right)-len(paths),'paths':paths})
    return {'method':'Estimated cross-sensor associations and monotone endpoint-constrained motion; not verified identities or DeepCTM forecasts','links':links,'limitations':['Unknown clock offsets, turning traffic and occlusion can invalidate associations.','Only unambiguous supported candidates are drawn; missing associations remain blank.','No signal state is inferred. Colors are estimated speed.']}
