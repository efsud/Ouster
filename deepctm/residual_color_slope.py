"""Requested speed-color/constant-slope matching of unclaimed endpoints only."""
from collections import defaultdict
from datetime import datetime
from bisect import bisect_left,bisect_right
from .color_slope import associate, METHOD
from .spatial_bridges import endpoint,reconstruct
from .local_gaps import VEHICLES


class Reservations:
    def __init__(self,paths=()):
        self.ends=defaultdict(list)
        for p in paths:self.add(p)

    def add(self,p):
        sites=p.get('sites') or [p['site'],p['site']]
        for site,side,point in ((sites[0],True,p['points'][0]),(sites[-1],False,p['points'][-1])):
            self.ends[site,side,p['direction']].append((point,p.get('identity_key')))

    def occupied(self,ep,side):
        for point,key in self.ends.get((ep['site'],side,ep['direction']),[]):
            if key and ep.get('identity') and key!=ep['identity']:continue
            if abs(point[0]-ep['t'])<.02 and abs(point[1]-ep['x'])<=.051:return True
        return False


def local_eligible(a,b):
    sign=1 if a['direction']=='eastbound' else -1
    if min(a['v']*sign,b['v']*sign)<0 or (b['x']-a['x'])*sign<0:return False
    same=a.get('identity') and a['identity']==b.get('identity')
    if not same and a['class_type']!=b['class_type']:return False
    if a.get('parent')==b.get('parent') and same:
        # An internal sampling hole already passed collection clock checks.
        return 1.5<b['t']-a['t']<=3
    try:
        dt=(datetime.fromisoformat(b['sensor_time'])-datetime.fromisoformat(a['sensor_time'])).total_seconds()
        if not .8<=dt/(b['t']-a['t'])<=1.2:return False
        if abs(b['lateral']-a['lateral'])>2:return False
    except (KeyError,TypeError,ValueError,ZeroDivisionError):return False
    ma=a.get('movement');mb=b.get('movement')
    if ma and mb and ma!=mb:return False
    return True


def remaining_matches(left,right,reservations,**kwargs):
    ai=[i for i,a in enumerate(left) if not reservations.occupied(a,True)]
    bi=[j for j,b in enumerate(right) if not reservations.occupied(b,False)]
    selected=associate([left[i] for i in ai],[right[j] for j in bi],**kwargs)
    return [dict(m,left=ai[m['left']],right=bi[m['right']]) for m in selected]


def generate(snapshot,existing):
    reserved=Reservations(existing['within_intersection']+existing['between_intersections'])
    local=[];between=[]
    for site in snapshot['sites']:
        groups=defaultdict(list)
        observed=defaultdict(list)
        for parent,tr in enumerate(site['tracks']):
            if tr.get('method') or tr['class_type'] not in VEHICLES:continue
            observed[tuple(tr.get('source_key',[])[:2])].extend(p[0] for p in tr['points'])
            parts=[[]]
            for p in tr['points']:
                if parts[-1] and p[0]-parts[-1][-1][0]>1.5:parts.append([])
                parts[-1].append(p)
            for part in parts:groups[tr['direction']].append((parent,tr,part))
        observed={key:sorted(times) for key,times in observed.items()}
        def eligible(a,b):
            if not local_eligible(a,b):return False
            # Never draw through intervening recorded observations of either
            # proposed identity, including a temporary classification change.
            for key in (tuple(a['identity']),tuple(b['identity'])):
                times=observed.get(key,[])
                if bisect_right(times,a['t']+.02)<bisect_left(times,b['t']-.02):return False
            return True
        for direction,fragments in groups.items():
            ends=[];starts=[]
            for index,(parent,tr,part) in enumerate(fragments):
                key=tr.get('source_key',[])
                if len(key)!=3:continue
                for target,is_exit in ((ends,True),(starts,False)):
                    e=endpoint(part,is_exit)
                    if not e:continue
                    side='end' if is_exit else 'start';outer=part[-1 if is_exit else 0]==tr['points'][-1 if is_exit else 0]
                    target.append(dict(e,site=site['id'],direction=direction,fragment=index,parent=parent,identity=key[:2],session=key[0],class_type=tr['class_type'],
                        sensor_time=tr.get('sensor_'+side) if outer else None,lateral=tr.get('lateral_'+side+'_m') if outer else None,movement=tr.get('movement',{}).get('movement')))
            for m in remaining_matches(ends,starts,reserved,max_gap=90,max_residual=10,eligible=eligible):
                a,b=ends[m['left']],starts[m['right']];same=a['identity']==b['identity']
                p=dict(site=site['id'],direction=direction,class_type=a['class_type'],identity_key=a['identity'] if same else None,
                    endpoint_identities=[a['identity'],b['identity']],method=METHOD,source='inferred',layer='residual_color_slope',identity='same_sensor_session_id' if same else 'unverified_local_association',
                    **{k:v for k,v in m.items() if k not in ('left','right')})
                local.append(p);reserved.add(p)
    def matcher(left,right):
        # spatial_bridges supplies direction in the surrounding link, while
        # signed velocity gives the same label for its admitted moving ends.
        left=[dict(e,direction='eastbound' if e['v']>0 else 'westbound') for e in left]
        right=[dict(e,direction='eastbound' if e['v']>0 else 'westbound') for e in right]
        return remaining_matches(left,right,reserved)
    links=reconstruct(snapshot,matcher=matcher)['links']
    for link in links:
        for q in link['paths']:
            p=dict(sites=link['sites'],direction=link['direction'],class_type=q['class_type'],points=q['points'],method=METHOD,layer='residual_color_slope',source='inferred',
                identity='unverified_cross_sensor_association',association_cost=q['association_cost'])
            between.append(p)
    return dict(method=METHOD,within_intersection=local,between_intersections=between,
        parameters=dict(color_band_mps=1,constant_slope_fraction=.8,max_tail_speed_adjustment_mps=.5,local_max_gap_s=90,between_max_gap_s=120,local_residual_m=10,between_residual_m=20),
        limitations=['Requested chronological same-color nearest-distance method, applied only to endpoints unused by existing estimates.',
            'First 80% retains original slope; final 20% makes a bounded endpoint correction. Observed segments are unchanged.',
            'Same color is not identity proof. Ties and unsuitable candidates remain unmatched.'])
