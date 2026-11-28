"""Prospective two-phase review of visible instantaneous boundary-speed retry.

Uses retained SDK endpoint timestamps/lateral observations for the same local
admission gates as production. Isolated masks and synchronized sensor-outage
masks are separate experiments. Hidden samples are saved only as scoring truth.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import time

import numpy as np

from .corridor_campaign import atomic, identity
from .endpoint_context import select
from .instantaneous_boundary_retry import (DEFAULTS, NOISE_EXCLUDED_SITES, VERSION,
                                           NOISE_POLICY, established_prediction, reconstruct)
from .reconstruction_study import metrics, summarize
from .same_id_gaps import candidates
from .spatial_bridges import endpoint

GAPS = (2, 3, 5, 10, 20, 30, 60)
BANDS = ((1.5,3.),(3.,5.),(5.,10.),(10.,20.),(20.,30.),(30.,60.))
CANDIDATES = {f'delta{delta:g}_fit{residual:g}': DEFAULTS | dict(
    max_speed_adjustment_mps=float(delta), max_fit_rmse_m=float(residual), max_fit_error_m=float(3*residual))
    for delta in (1, 2, 4) for residual in (.1, .2)}
LOCAL_LATERAL_SITES = {'OBC-AG-SA-C251068', 'OBC-AG-SA-C257222', 'OBC-AG-SA-C257223',
                       'OBC-AG-SA-C257236', 'OBC-AG-SA-C257227'}


def implementation_hashes():
    directory=Path(__file__).resolve().parent
    names=('instantaneous_boundary_retry.py','validate_instantaneous_boundary.py',
           'same_id_gaps.py','spatial_bridges.py','endpoint_context.py','endpoint_speed.py',
           'trajectory_reconstruction.py','adaptive_endpoint_grid.py','stationary_plateau.py',
           'lateral_gap.py','reconstruction_layers.py','reconstruction_study.py','corridor_campaign.py')
    return {name:hashlib.sha256((directory/name).read_bytes()).hexdigest() for name in names}


def baseline_configuration():
    root=Path(__file__).resolve().parents[1]
    names=('florida-endpoint-speed','stationary-plateau','adaptive-grid','same-class-recovery',
           'florida-local-lateral','florida-gap-integrity')
    policies={name:json.loads((root/f'config/reconstruction/{name}.json').read_text()) for name in names}
    endpoint_policy=policies['florida-endpoint-speed']
    assert endpoint_policy['parameters']==NOISE_POLICY
    assert set(endpoint_policy['excluded_sites'])==NOISE_EXCLUDED_SITES
    assert all('florida' in policies[name]['enabled_regions'] for name in ('stationary-plateau','adaptive-grid','same-class-recovery'))
    assert policies['florida-local-lateral']['enabled'] and policies['florida-local-lateral']['max_gap_s']==10
    assert set(policies['florida-local-lateral']['enabled_sites'])==LOCAL_LATERAL_SITES
    assert policies['florida-gap-integrity']['stationary_admission'] and policies['florida-gap-integrity']['terminal_chains']
    return {name:dict(sha256=hashlib.sha256((root/f'config/reconstruction/{name}.json').read_bytes()).hexdigest(),
                      configuration=policies[name]) for name in names}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def summary(rows, method):
    accepted = [r for r in rows if method in r['metrics']]
    added = [r for r in accepted if 'baseline' not in r['metrics']]
    common = [r for r in accepted if 'baseline' in r['metrics']]
    def stat(selected):
        return dict(cases=len(selected), independent_ids=len({r['identity_hash'] for r in selected}),
                    quality=summarize([r['metrics'][method] for r in selected]))
    return dict(eligible=len(rows), eligible_ids=len({r['identity_hash'] for r in rows}),
        admitted=sum(r.get('admitted', False) for r in rows), accepted=stat(accepted), added=stat(added),
        common=stat(common), baseline_preserved=all(r['metrics'][method] == r['metrics']['baseline'] for r in common),
        per_site={s: stat([r for r in added if r['site']==s]) for s in sorted({r['site'] for r in rows})},
        per_gap={str(g): stat([r for r in added if r['gap_s']==g]) for g in GAPS},
        per_actual_duration_band={f'{lo:g}-{hi:g}':stat([r for r in added if lo<r['actual_gap_s']<=hi]) for lo,hi in BANDS},
        per_site_actual_duration_band={site:{f'{lo:g}-{hi:g}':stat([r for r in added if r['site']==site and lo<r['actual_gap_s']<=hi])
                                            for lo,hi in BANDS} for site in sorted({r['site'] for r in rows})},
        outside_duration_scope=stat([r for r in added if r['actual_gap_s']>60]),
        per_mode={mode: stat([r for r in added if r['mode']==mode]) for mode in ('isolated', 'all_vehicle_outage')},
        per_regime={regime: stat([r for r in added if r.get('regime')==regime]) for regime in ('stopped','moving','transition')})


class EndpointEvidence:
    def __init__(self, path, snapshot):
        self.db = sqlite3.connect(f'file:{Path(path).resolve()}?mode=ro', uri=True)
        self.snapshot = snapshot; self.cache = {}

    def observation(self, site, track, offset):
        i = next((i for i, p in enumerate(track['points']) if abs(p[0]-offset)<1e-7), None)
        if i is None:
            return None
        offsets = track.get('original_receipt_offsets_s')
        received = self.snapshot['start']+(offsets[i] if offsets is not None else offset)
        key = (site['id'], track['source_key'][0], round(received, 4))
        if key not in self.cache:
            row = self.db.execute('SELECT payload FROM frames WHERE site=? AND session=? AND received BETWEEN ? AND ? ORDER BY abs(received-?) LIMIT 1',
                (key[0], key[1], received-.02, received+.02, received)).fetchone()
            self.cache[key] = json.loads(row[0]) if row else None
        raw = self.cache[key]
        if raw is None:
            return None
        frame = raw.get('frame', {})
        obj = next((o for o in frame.get('objects', []) if str(o.get('id')) == str(track['source_key'][1])), None)
        stamp = frame.get('timestamp') or raw.get('timestamp')
        transform = self.snapshot.get('transform_manifest', {}).get('sites', {}).get(site['id'])
        if obj is None or not stamp or not transform or 'projection_bearing_deg' not in site:
            return None
        angle = math.radians(transform['rotation_deg']-site['projection_bearing_deg'])
        x = float(obj['centerX']); y = float(obj['centerY'])*(-1 if transform['mirror_y'] else 1)
        lateral = math.sin(angle)*x+math.cos(angle)*y
        return dict(timestamp=stamp, lateral_m=lateral)

    def close(self):
        self.db.close()


def local_cases(snapshot, lo, hi, maximum, excluded_ids=()):
    """Same fixed masks for every method; selection independent of errors."""
    excluded = set(excluded_ids); pools = defaultdict(dict); outage_windows = {}
    for site in snapshot['sites']:
        for track in site['tracks']:
            key = identity(site, track)
            if track.get('class_type') != '2' or track.get('method') or key in excluded:
                continue
            p = np.asarray(track['points'], float)
            if len(p)<14 or p[0,0]<lo or p[-1,0]>hi or np.any(np.diff(p[:,0])<=0) or np.any(np.diff(p[:,0])>1.5):
                continue
            rank = hashlib.sha256(key.encode()).hexdigest()
            for gap in GAPS:
                windows = [('isolated', .5*(p[0,0]+p[-1,0])-gap/2, None)]
                # Shared window starts across every object and sensor. The
                # outage evidence concerns the controlled mask, not a fabricated
                # event in the original recording.
                for start in np.arange(lo+60, hi-gap-30, 120):
                    windows.append(('all_vehicle_outage', float(start), (float(start), float(start+gap))))
                for mode, start, outage in windows:
                    if start < p[0,0]+2.5 or start+gap > p[-1,0]-2.5:
                        continue
                    i = int(np.searchsorted(p[:,0], start, side='right')-1)
                    j = int(np.searchsorted(p[:,0], start+gap))
                    if i<5 or len(p)-j<5 or j-i<3:
                        continue
                    before, after = p[:i+1].tolist(), p[j:].tolist()
                    a, b = endpoint(before, True), endpoint(after, False)
                    if a is None or b is None:
                        continue
                    # Derive direction from visible flanks only, excluding the
                    # concealed displacement between them.
                    signed = sum(q[-1][1]-q[0][1] for q in (before,after))
                    travelled = sum(sum(abs(v[1]-u[1]) for u,v in zip(q,q[1:])) for q in (before,after))
                    if abs(signed)<3 or abs(signed)<.7*travelled:
                        continue
                    direction = 'eastbound' if signed>0 else 'westbound'
                    truth = p[i+1:j].copy(); truth[:,1] *= 1 if direction=='eastbound' else -1
                    entry = (rank, site, track, gap, mode, before, after, a, b, truth, direction, outage)
                    # At most one case per identity/gap/mode, earliest shared
                    # outage if a long continuous object crosses several.
                    pools[site['id'],direction,gap,mode].setdefault(rank, entry)
                    if outage:
                        outage_windows.setdefault(outage, {})
    chosen = [value for pool in pools.values() for _,value in sorted(pool.items())[:maximum]]
    # Audit the all-object mask itself. No retained object positions inside any
    # selected outage are passed to predictors or peer functions.
    for start,end in outage_windows:
        for site in snapshot['sites']:
            removed = [(digest(track.get('source_key',[])[:2]), p) for track in site['tracks']
                       for p in track['points'] if start<p[0]<end]
            outage_windows[start,end][site['id']] = dict(removed_observations=len(removed),
                                                        hidden_observation_sha256=digest(removed))
    return chosen, [dict(start=a,end=b,sites=v) for (a,b),v in sorted(outage_windows.items())]


def evaluate(snapshot, buffer, report, configurations, lo, hi, maximum=5,
             excluded_ids=(), examples_path=None):
    cases, outage_audit = local_cases(snapshot, lo, hi, maximum, excluded_ids)
    raw = EndpointEvidence(buffer, snapshot); rows=[]; reasons=Counter(); examples=[]
    params = report['calibration']['parameters']; clock=time.monotonic()
    for n,(rank,site,track,gap,mode,left,right,a,b,truth,direction,outage) in enumerate(cases):
        row=dict(site=site['id'],identity_hash=rank,gap_s=gap,actual_gap_s=b['t']-a['t'],
                 mode=mode,start_s=a['t'],end_s=b['t'],admitted=False,metrics={},states={})
        ea,eb=raw.observation(site,track,a['t']),raw.observation(site,track,b['t'])
        if ea is None or eb is None:
            row['reason']='missing_raw_endpoint_evidence'; reasons[row['reason']]+=1; rows.append(row);continue
        before=dict(track,points=left,direction=direction,movement={'state':'unknown'},
                    sensor_end=ea['timestamp'],lateral_end_m=ea['lateral_m'])
        after=dict(track,points=right,direction=direction,movement={'state':'unknown'},
                   sensor_start=eb['timestamp'],lateral_start_m=eb['lateral_m'])
        pair=dict(site,tracks=[before,after],observation_gaps=[list(outage)] if outage else [])
        # For outage tests, these flanks are the only object observations passed
        # to admission and prediction. All other vehicles in the window are
        # withheld, as documented by outage_audit, and never supply priors.
        audit=[]; admitted=list(candidates(pair,include_same_class=True,
            allow_stationary_noise=site['id'] not in NOISE_EXCLUDED_SITES,audit=audit.append))
        lateral=False
        if not admitted and site['id'] in LOCAL_LATERAL_SITES and b['t']-a['t']<=10:
            admitted=list(candidates(pair,include_same_class=True,allow_lateral_motion=True))
            lateral=bool(admitted and admitted[0].get('requires_lateral_check'))
        if not admitted:
            row['reason']=audit[-1]['reason'] if audit else 'no_admitted_candidate'
            reasons[row['reason']]+=1; rows.append(row);continue
        candidate=admitted[0]; row['admitted']=True
        a,b=candidate['a'],candidate['b']
        base=established_prediction(site['id'],a,b,report,candidate['classes'],candidate.get('stationary_noise_admission',False))
        if lateral:
            from .reconstruction_layers import prediction
            base=prediction(a,b,report,exact_join=True)
            # Missing per-sample lateral support is a real admission failure,
            # not permission to pretend this active baseline branch is absent.
            from .lateral_gap import supports
            for frag,values,exit_side,label in ((before,left,True,'lateral_end_context'),(after,right,False,'lateral_start_context')):
                context=[]
                for point in select(values,exit_side):
                    obs=raw.observation(site,track,point[0])
                    if obs:context.append([point[0],obs['lateral_m']])
                frag[label]=context
            if base is not None:
                ok,_=supports(before,after,base)
                if not ok:base=None
        sign=1 if direction=='eastbound' else -1
        regime=('stopped' if np.max(truth[:,2])<.5 else 'moving' if np.min(truth[:,2])>=1 else 'transition')
        row['regime']=regime
        if base is not None:
            p=np.asarray(base).copy();p[:,1]*=sign
            row['metrics']['baseline']=metrics(p,truth,params)
        for name,cfg in configurations.items():
            if base is not None:
                row['metrics'][name]=row['metrics']['baseline'];row['states'][name]='baseline_retained';continue
            proposal=reconstruct(site['id'],left,right,a,b,direction,report,cfg,candidate['classes'],established=None)
            row['states'][name]=proposal['state']
            if proposal['state']!='candidate':
                reasons[name+':'+proposal.get('reason',proposal['state'])]+=1;continue
            if lateral:
                ok,_=supports(before,after,proposal['points'])
                if not ok:
                    row['states'][name]='lateral_support_rejected';continue
            pred=proposal['points'].copy();pred[:,1]*=sign
            row['metrics'][name]=metrics(pred,truth,params)
            if len(examples)<20:
                original_truth=truth.copy();original_truth[:,1]*=sign
                examples.append(dict(site=site['id'],identity_hash=rank,gap_s=gap,mode=mode,method=name,
                    before=left,after=right,hidden_truth=original_truth.tolist(),prediction=proposal['points'].tolist(),
                    boundary_fits=proposal['boundary_fits'],metrics=row['metrics'][name]))
        rows.append(row)
        if n%100==0:print(json.dumps(dict(evaluated=n+1,total=len(cases),elapsed_s=round(time.monotonic()-clock,1))),flush=True)
    raw.close()
    if examples_path:atomic(Path(examples_path),dict(recording_start=snapshot['start'],examples=examples))
    return dict(cases=rows,methods={name:summary(rows,name) for name in ['baseline',*configurations]},
                reasons=dict(reasons),outage_masks=outage_audit,elapsed_s=round(time.monotonic()-clock,2))


def quality_gate(stat, minimum=10):
    q=stat['quality']
    return bool(stat['independent_ids']>=minimum and q.get('mae_m',999)<=1. and
        q.get('p95_case_mae_m',999)<=3. and q.get('speed_mae_mps',999)<=.75 and q.get('physics_violation',1)==0)


def develop(snapshot, buffer, output, lo=1800, hi=3540, maximum=20):
    folder=Path(output);folder.mkdir(parents=True,exist_ok=True)
    if (folder/'protocol.json').exists():raise ValueError('Protocol already exists; do not overwrite frozen review')
    root=Path(__file__).resolve().parents[1];raw=Path(snapshot).read_bytes();s=json.loads(raw)
    report=json.loads((root/'data/reconstruction/word-v1-collection/evaluation-001/report.json').read_text())
    protocol=dict(version=VERSION,created_at=time.time(),development_source=str(Path(snapshot).resolve()),
        review_revision=4,
        snapshot_sha256=hashlib.sha256(raw).hexdigest(),development_offsets=[lo,hi],development_window=[s['start']+lo,s['start']+hi],
        final_test_not_before_epoch=s['end']+60,final_maximum_per_site_direction_gap_mode=maximum,
        candidate_configurations=CANDIDATES,gaps_s=GAPS,methods=['production_baseline','visible_boundary_retry'],
        baseline_configuration=baseline_configuration(),
        implementation_sha256=implementation_hashes(),
        baseline_report_sha256=hashlib.sha256((root/'data/reconstruction/word-v1-collection/evaluation-001/report.json').read_bytes()).hexdigest(),
        mask_modes=['isolated','all_vehicle_outage'],minimum_training='No fitted global model; fixed physical limits inherited from previously deployed calibration.',
        parameters=report['calibration']['parameters'],baseline_noise_policy=NOISE_EXCLUDED_SITES and list(sorted(NOISE_EXCLUDED_SITES)),
        baseline='kinematic0.01 + endpoint noise correction exceptHattaway + stationary admission/plateau exceptHattaway + adaptivegrid + same-class + site-gated lateral recovery',
        selection_rule='Among candidates with >=10 new independent development IDs and meanMAE<=1m, p95caseMAE<=3m, speedMAE<=.75m/s, zero physics violations, choose most newly accepted IDs, then lowestMAE. Otherwise select smallest mean addedMAE for an explicitly unqualified test.',
        final_gate='Same global quality gate, >=5 new independent IDs at an enabled site in development and final; isolated and all-vehicle-outage modes each>=5 new IDs globally. Each enabled actual-duration band also>=5 new independent IDs plus quality in BOTH development and final. IN ADDITION every enabled site×actual-duration-band combination needs>=5 added independent IDs plus quality in BOTH development and final. Existing successes unchanged. Addedmaxerror<=10m. Actualdurations>60s never enabled.',
        deployment_duration_bands=BANDS,
        leakage_controls=['Hidden positions are scoring truth only. No hidden samples enter boundary fitting.',
            'All vehicles in controlled outage intervals withheld from prediction; no peer model.',
            'Raw SDK/lateral evidence from frozen buffer at visible endpoints; missing evidence excludes case.',
            'Existing session, direction, clock, lateral, class and long-gap outage admission gates retained.',
            'Final target IDs appearing anywhere in development recording are excluded; final interval is later and untouched.',
            'Configuration selection sealed before final test; no post-test tuning.'],
        limitations=['Provisional road projection and timestamp basis.',
            'Same-ID masking does not establish between-sensor identity or recover true outages.',
            'Independent vehicles, not repeated masks, determine support counts.'])
    atomic(folder/'protocol.json',protocol)
    dev=evaluate(s,buffer,report,CANDIDATES,lo,hi,maximum,examples_path=folder/'development_examples.json')
    atomic(folder/'development.json',dev)
    qualified=[name for name in CANDIDATES if quality_gate(dev['methods'][name]['added'])]
    choice=min(qualified or CANDIDATES,key=lambda name:(-dev['methods'][name]['added']['independent_ids'] if qualified else 0,
                 dev['methods'][name]['added']['quality'].get('mae_m',999),name))
    excluded=sorted({identity(site,tr) for site in s['sites'] for tr in site['tracks'] if identity(site,tr)})
    atomic(folder/'excluded_development_ids.json',excluded)
    selection=dict(version=VERSION,selected=choice,configuration=CANDIDATES[choice],development_qualified=bool(qualified),
        protocol_sha256=hashlib.sha256((folder/'protocol.json').read_bytes()).hexdigest(),
        excluded_ids_sha256=hashlib.sha256((folder/'excluded_development_ids.json').read_bytes()).hexdigest(),
        final_test_not_before_epoch=protocol['final_test_not_before_epoch'],frozen_at=time.time())
    atomic(folder/'selection.json',selection)
    print(json.dumps(dict(state='development_complete',selection=selection,selected_result=dev['methods'][choice])),flush=True)


def final(snapshot,buffer,output,maximum=None,test_after=None):
    folder=Path(output)
    if (folder/'final.json').exists() or (folder/'final_opened.json').exists():raise ValueError('Final test already opened; do not rescore/reselect')
    protocol=json.loads((folder/'protocol.json').read_text());selection=json.loads((folder/'selection.json').read_text())
    if selection['protocol_sha256']!=hashlib.sha256((folder/'protocol.json').read_bytes()).hexdigest():raise ValueError('Protocol changed')
    if protocol['baseline_configuration']!=baseline_configuration():raise ValueError('Production baseline policies changed since selection')
    if protocol['implementation_sha256']!=implementation_hashes():raise ValueError('Implementation changed since protocol was sealed')
    if selection['excluded_ids_sha256']!=hashlib.sha256((folder/'excluded_development_ids.json').read_bytes()).hexdigest():raise ValueError('Excluded identities changed')
    if selection['configuration']!=protocol['candidate_configurations'][selection['selected']]:raise ValueError('Selected configuration differs from frozen candidate')
    raw=Path(snapshot).read_bytes();s=json.loads(raw)
    effective_start=max(selection['final_test_not_before_epoch'],test_after or 0)
    lo=max(0,effective_start-s['start']);hi=s['end']-s['start']-30
    if hi-lo<300:raise ValueError('Need at least five minutes of unseen final data')
    excluded=json.loads((folder/'excluded_development_ids.json').read_text())
    root=Path(__file__).resolve().parents[1]
    report=json.loads((root/'data/reconstruction/word-v1-collection/evaluation-001/report.json').read_text())
    if hashlib.sha256((root/'data/reconstruction/word-v1-collection/evaluation-001/report.json').read_bytes()).hexdigest()!=protocol['baseline_report_sha256']:
        raise ValueError('Baseline calibration report changed')
    if report['calibration']['parameters']!=protocol['parameters']:
        raise ValueError('Baseline calibration parameters changed')
    atomic(folder/'final_opened.json',dict(opened_at=time.time(),source=str(Path(snapshot).resolve()),
        snapshot_sha256=hashlib.sha256(raw).hexdigest(),selection_sha256=hashlib.sha256((folder/'selection.json').read_bytes()).hexdigest(),offsets=[lo,hi],
        stricter_external_start_epoch=test_after,effective_start_epoch=effective_start))
    maximum=protocol['final_maximum_per_site_direction_gap_mode'] if maximum is None else maximum
    if maximum!=protocol['final_maximum_per_site_direction_gap_mode']:raise ValueError('Cannot change final sampling after selection')
    result=evaluate(s,buffer,report,{selection['selected']:selection['configuration']},lo,hi,maximum,excluded,folder/'final_examples.json')
    atomic(folder/'final.json',result)
    dev=json.loads((folder/'development.json').read_text())['methods'][selection['selected']]
    test=result['methods'][selection['selected']]
    sites=[site for site in test['per_site'] if quality_gate(test['per_site'][site],5) and quality_gate(dev['per_site'][site],5)]
    bands=[list(band) for band in BANDS if quality_gate(test['per_actual_duration_band'][f'{band[0]:g}-{band[1]:g}'],5)
           and quality_gate(dev['per_actual_duration_band'][f'{band[0]:g}-{band[1]:g}'],5)]
    joint={site:[band for band in bands if quality_gate(test['per_site_actual_duration_band'][site][f'{band[0]:g}-{band[1]:g}'],5)
                 and quality_gate(dev['per_site_actual_duration_band'][site][f'{band[0]:g}-{band[1]:g}'],5)] for site in sites}
    joint={site:bands for site,bands in joint.items() if bands}
    mode_ok=all(quality_gate(test['per_mode'][mode],5) for mode in ('isolated','all_vehicle_outage'))
    max_error=max([r['metrics'][selection['selected']]['max_error_m'] for r in result['cases']
                   if selection['selected'] in r['metrics'] and 'baseline' not in r['metrics']],default=float('inf'))
    eligible=bool(selection['development_qualified'] and quality_gate(test['added']) and joint and mode_ok and
                  test['baseline_preserved'] and max_error<=10)
    policy=dict(version=VERSION,enabled=eligible,enabled_sites=sorted(joint) if eligible else [],configuration=selection['configuration'],
        enabled_duration_bands=bands if eligible else [],
        enabled_site_duration_bands=joint if eligible else {},
        parameters=report['calibration']['parameters'],validation_state='complete',
        baseline_configuration=protocol['baseline_configuration'],implementation_sha256=protocol['implementation_sha256'],
        selection_sha256=hashlib.sha256((folder/'selection.json').read_bytes()).hexdigest(),evidence=str(folder/'report.json'))
    atomic(folder/'policy.json',policy)
    review=dict(state='complete',selection=selection,development=dev,final=test,maximum_added_error_m=None if not np.isfinite(max_error) else max_error,
        deployment_eligible=eligible,enabled_sites=policy['enabled_sites'],enabled_duration_bands=policy['enabled_duration_bands'],
        enabled_site_duration_bands=policy['enabled_site_duration_bands'],mode_quality_qualified=mode_ok,
        limitations=protocol['limitations'])
    atomic(folder/'report.json',review);print(json.dumps(review),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['develop','final']);p.add_argument('--snapshot',required=True)
    p.add_argument('--buffer',required=True);p.add_argument('--output',required=True);p.add_argument('--maximum',type=int)
    p.add_argument('--test-after',type=float)
    a=p.parse_args()
    if a.phase=='develop':develop(a.snapshot,a.buffer,a.output,maximum=a.maximum or 20)
    else:final(a.snapshot,a.buffer,a.output,a.maximum,a.test_after)
