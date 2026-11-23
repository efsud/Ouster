"""Aggregate platoon-lag diagnostic, never a cross-sensor identity decoder.

First-half lag selection; later-half correlation is reported separately. Signal
cycles and unknown relative sensor latency can create aliased peaks. No matching
policy is changed by this diagnostic.
"""
import argparse,json
from pathlib import Path
import numpy as np
from scipy.ndimage import gaussian_filter1d
from .spatial_bridges import reconstruct
from .corridor_campaign import atomic

def profile(a,b,min_lag,max_lag,bin_seconds=5):
    a=np.asarray(a,float);b=np.asarray(b,float);rows=[]
    for lag in range(max(0,int(np.ceil(min_lag/bin_seconds))),int(max_lag/bin_seconds)+1):
        x=a[:len(a)-lag] if lag else a;y=b[lag:] if lag else b
        if len(x)<20 or np.std(x)<1e-8 or np.std(y)<1e-8:continue
        rows.append({'lag_s':lag*bin_seconds,'correlation':float(np.corrcoef(x,y)[0,1])})
    return sorted(rows,key=lambda x:-x['correlation'])

def evaluate(snapshot,params):
    groups=[]
    def collect(left,right):groups.append((left,right));return []
    links=reconstruct(snapshot,matcher=collect)['links'];byid={s['id']:s for s in snapshot['sites']};records=[];index=0
    for link in links:
        if 'reason' in link:records.append({'sites':link['sites'],'direction':link['direction'],'state':'insufficient_endpoints'});continue
        left,right=groups[index];index+=1
        if not left or not right:continue
        lists=[]
        for sid,points,exit_side in zip(link['sites'],(left,right),(True,False)):
            selected={}
            for ep in points:
                key=tuple(byid[sid]['tracks'][ep['fragment']]['source_key'][:2]);old=selected.get(key)
                sign=1 if link['direction']=='eastbound' else -1
                if old is None or (ep['x']-old['x'])*sign*(1 if exit_side else -1)>0:selected[key]=ep
            lists.append(list(selected.values()))
        departure,arrival=lists
        distance=abs(np.median([p['x'] for p in right])-np.median([p['x'] for p in left]));minimum=distance/params['vmax']
        bins=np.arange(0,3600+5,5)
        a=np.histogram([p['t'] for p in departure],bins)[0];b=np.histogram([p['t'] for p in arrival],bins)[0]
        # Smooth each partition separately: future counts cannot leak into selection.
        at,bt=[gaussian_filter1d(x[:360].astype(float),2) for x in (a,b)]
        av,bv=[gaussian_filter1d(x[360:].astype(float),2) for x in (a,b)]
        train=profile(at,bt,minimum,360);later=profile(av,bv,minimum,360)
        if not train or not later:records.append({'sites':link['sites'],'direction':link['direction'],'state':'insufficient_variation'});continue
        chosen=train[0];alternatives=[r for r in train if abs(r['lag_s']-chosen['lag_s'])>=30]
        margin=chosen['correlation']-alternatives[0]['correlation'] if alternatives else None
        held=next((r['correlation'] for r in later if r['lag_s']==chosen['lag_s']),None)
        records.append({'sites':link['sites'],'names':link['names'],'direction':link['direction'],'state':'diagnostic_only',
            'endpoint_counts':[len(departure),len(arrival)],'estimated_coverage_gap_m':float(distance),'physical_minimum_s':float(minimum),
            'selected_training_lag_s':chosen['lag_s'],'training_correlation':chosen['correlation'],'alternative_peak_margin':margin,
            'heldout_correlation_at_selected_lag':held,'heldout_best_lag_s':later[0]['lag_s'],
            'training_profile':train,'heldout_profile':later,'stable_peak':bool(margin is not None and margin>=.1 and held is not None and held>=.5 and abs(later[0]['lag_s']-chosen['lag_s'])<=20)})
    return {'window':[snapshot['start'],snapshot['end']],'links':records,'limitations':['Aggregate correlation cannot establish vehicle identity.','Signal periodicity and unknown clock offsets can alias travel-time peaks.','Not a calibrated CTM, routing model or signal map.','No estimates published from this diagnostic.']}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--region',choices=['florida','finch'],required=True);p.add_argument('--output',required=True);a=p.parse_args()
    s=json.loads(Path(f'data/{a.region}-rolling/snapshot.json').read_text());params=json.loads(Path(f'data/reconstruction/eight-hour-20261123/{a.region}/model.json').read_text())['parameters'];r=evaluate(s,params);atomic(Path(a.output),r)
    print(json.dumps([{k:v for k,v in x.items() if 'profile' not in k} for x in r['links']],indent=2))
