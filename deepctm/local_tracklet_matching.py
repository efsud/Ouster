"""Retrospective same-site identity-change hypotheses, never observed identities."""
from datetime import datetime
from .spatial_bridges import endpoint
from .global_association import solve_edges


def candidate(a,b):
    ka,kb=a.get('source_key',[]),b.get('source_key',[])
    if len(ka)!=3 or len(kb)!=3 or ka[0]!=kb[0] or ka[1]==kb[1]:return None
    if a.get('class_type')!='2' or b.get('class_type')!='2' or a['direction']!=b['direction']:return None
    # Only a supported same through movement. No arbitrary turning/FIFO join.
    movement=a.get('movement',{}).get('movement')
    if movement not in ('WE','EW') or movement!=b.get('movement',{}).get('movement'):return None
    left=endpoint(a['points'],True);right=endpoint(b['points'],False)
    if not left or not right:return None
    dt=right['t']-left['t']
    if not 1.5<dt<=30:return None
    try:
        lateral=abs(a['lateral_end_m']-b['lateral_start_m'])
        ratio=(datetime.fromisoformat(b['sensor_start'])-datetime.fromisoformat(a['sensor_end'])).total_seconds()/dt
    except (KeyError,ValueError,TypeError):return None
    if lateral>1.25 or not .8<=ratio<=1.2:return None
    sign=1 if a['direction']=='eastbound' else -1
    dx=(right['x']-left['x'])*sign;v0=left['v']*sign;v1=right['v']*sign
    if min(v0,v1)<-.25 or dx<0 or dx/dt>30:return None
    expected=max(0,(v0+v1)/2)*dt
    # Local stop/go allowed, but broad ambiguous motion remains unassociated.
    residual=abs(dx-expected)/max(5.,.35*expected)
    cost=residual+abs(v1-v0)/15+lateral/2.5
    if cost>1.5:return None
    return left,right,cost


def reconstruct(site,predict,reserved=()):
    tracks=site['tracks'];edges={};paths={};blocked=set(reserved)
    used_ends={a for a,b in blocked};used_starts={b for a,b in blocked}
    for i,a in enumerate(tracks):
        if a.get('class_type')!='2':continue
        if round(a['points'][-1][0],2) in used_ends:continue
        for j,b in enumerate(tracks):
            if round(b['points'][0][0],2) in used_starts:continue
            proposal=candidate(a,b)
            if proposal is None:continue
            left,right,cost=proposal
            points=predict(left,right)
            if points is None:continue
            edges[i,j]=cost;paths[i,j]=points
    # Both endpoint alternatives and global assignment alternatives must separate.
    selected=solve_edges(len(tracks),len(tracks),edges,unmatched_cost=.75,margin=.5)
    result=[]
    for m in selected:
        i,j=m['left'],m['right'];cost=m['cost']
        rivals=[v for (a,b),v in edges.items() if (a==i or b==j) and (a,b)!=(i,j)]
        if rivals and min(rivals)-cost<.5:continue
        result.append(dict(site=site['id'],direction=tracks[i]['direction'],class_type='2',points=paths[i,j],
            source='inferred',method='kinematic_tracklet_association',identity='unverified_same_site_changed_id',
            gap_kind='changed_track_id',gap_s=paths[i,j][-1][0]-paths[i,j][0][0],association_cost=cost,ambiguity_margin=m['margin']))
    return result
