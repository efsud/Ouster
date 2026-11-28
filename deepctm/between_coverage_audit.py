"""Audit blind roadway versus overlapping sensor coverage without inventing paths.

Overlap associations remain hypotheses and never enter KPI vehicle counts.
A negative signed end-to-start distance is observed overlap, not a backwards gap.
"""
import argparse
from bisect import bisect_right
from collections import Counter
import hashlib
import json
from pathlib import Path
import time
import numpy as np
from .fragment_terminals import mark
from .global_association import solve_edges
from .overlap_association import evidence
from .residual_color_slope import Reservations
from .spatial_bridges import reconstruct


def overlap_link(left,right,up,down,reservations=None):
    sign=1 if up['station_m']<down['station_m'] else -1
    direction='eastbound' if sign==1 else 'westbound'
    reserved=reservations or Reservations()
    def views(group,site,departure):
        rows=[]
        for index,ep in enumerate(group):
            if reserved.occupied(dict(ep,direction=direction),departure):continue
            track=site['tracks'][ep['fragment']]
            p=np.asarray(track['points'],float)
            rows.append(dict(index=index,endpoint=ep,track=dict(track,points=p),
                begin=float(p[0,0]),end=float(p[-1,0]),lo=float(p[:,1].min()),hi=float(p[:,1].max())))
        return rows
    aa=views(left,up,True);bb=sorted(views(right,down,False),key=lambda r:r['begin']);starts=[b['begin'] for b in bb]
    records={};edges={};motion={};counts=Counter()
    for a in aa:
        for b in bb[:bisect_right(starts,a['end']-1)]:
            if b['end']<a['begin']+1:continue
            counts['concurrent_pairs']+=1
            if min(a['hi'],b['hi'])-max(a['lo'],b['lo'])<10:continue
            counts['shared_space_pairs']+=1
            ev=evidence(a['track'],b['track'])
            if ev is None:continue
            pair=a['index'],b['index']
            if ev['motion_cost']<1.5:motion[pair]=ev['motion_cost']
            if ev['cost']<1.5:edges[pair]=ev['cost'];records[pair]=ev
    baseline={(m['left'],m['right']) for m in solve_edges(len(left),len(right),motion,margin=.5)}
    matches=[]
    for m in solve_edges(len(left),len(right),edges,margin=.5):
        key=m['left'],m['right'];ev=records[key]
        if ev['shape_discrepancy'] is None and key not in baseline:continue
        a,b=left[key[0]],right[key[1]]
        matches.append(dict(upstream_fragment=a['fragment'],downstream_fragment=b['fragment'],
            upstream_local_key=up['tracks'][a['fragment']].get('source_key'),downstream_local_key=down['tracks'][b['fragment']].get('source_key'),
            margin=m['margin'],evidence=ev))
    out=dict(sites=[up['id'],down['id']],names=[up['name'],down['name']],direction=direction,
        departures=len(left),arrivals=len(right),unused_departures=len(aa),unused_arrivals=len(bb),
        feasible_overlap_pairs=len(edges),overlap_hypotheses=len(matches),counts=dict(counts),hypotheses=matches)
    if matches:
        m=max(matches,key=lambda r:r['evidence']['support_s'])
        out['example']=dict(source_keys=[m['upstream_local_key'],m['downstream_local_key']],
            overlap_time=m['evidence']['overlap_time'],evidence=m['evidence'])
    if left and right:
        u=float(np.median([e['x'] for e in left]));v=float(np.median([e['x'] for e in right]))
        out.update(median_upstream_end_m=u,median_downstream_start_m=v,median_signed_end_to_start_m=(v-u)*sign)
    else:out['median_signed_end_to_start_m']=None
    return out


def audit(snapshot,layers):
    # Exactly the production car-class scope; other classes are not silently pooled.
    s=dict(snapshot,sites=[dict(site,tracks=[t for t in site['tracks'] if t['class_type']=='2']) for site in snapshot['sites']])
    s=mark(s,layers['within_intersection']);sites={site['id']:site for site in s['sites']}
    existing=layers['within_intersection']+layers['between_intersections']
    extra=layers.get('residual_color',{})
    existing+=extra.get('within_intersection',[])+extra.get('between_intersections',[])
    reservations=Reservations(existing);links=[]
    def inspect(left,right):
        if left and right:links.append(overlap_link(left,right,sites[left[0]['site']],sites[right[0]['site']],reservations))
        return []
    coverage=reconstruct(s,matcher=inspect)
    # Preserve insufficient-coverage links too: always represent all12 directions.
    by_key={(tuple(x['sites']),x['direction']):x for x in links}
    output=[]
    for link in coverage['links']:
        key=tuple(link['sites']),link['direction']
        output.append(by_key.get(key,dict(sites=link['sites'],names=link['names'],direction=link['direction'],reason=link.get('reason','No usable endpoint group'),overlap_hypotheses=0,hypotheses=[],median_signed_end_to_start_m=None)))
    return dict(window=[snapshot['start'],snapshot['end']],snapshot_generated_at=snapshot['generated_at'],links=output,
        limitations=['No missing trajectory positions are drawn inside observed overlapping coverage.',
            'Overlap hypotheses do not verify cross-sensor vehicle identity or clock/alignment accuracy.',
            'Hypotheses exclude endpoints occupied by existing gap estimates; counts are conditional on those hypotheses.',
            'Endpoint counts describe fragments, not distinct vehicles. Negative median gap indicates overlapping projected coverage.'])


def main():
    p=argparse.ArgumentParser();p.add_argument('--snapshot',required=True);p.add_argument('--layers',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    start=time.monotonic();raw=Path(a.snapshot).read_bytes();s=json.loads(raw);layers=json.loads(Path(a.layers).read_text())
    if s['generated_at']!=layers['snapshot_generated_at']:raise ValueError('Snapshot and estimates must match')
    result=audit(s,layers);result.update(source_sha256=hashlib.sha256(raw).hexdigest(),elapsed_s=time.monotonic()-start)
    path=Path(a.output);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(result,indent=2))
    print(json.dumps(dict(elapsed_s=result['elapsed_s'],links=[{k:l[k] for k in ('names','direction','median_signed_end_to_start_m','overlap_hypotheses')} for l in result['links']])),flush=True)

if __name__=='__main__':main()
