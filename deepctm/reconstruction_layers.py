"""Build two explicitly inferred layers after the study has selected a method.
No estimates enter observations, calibration, or KPI inputs.
"""
import argparse,json,time,fcntl
from pathlib import Path
from collections import defaultdict
import numpy as np
from .trajectory_reconstruction import baseline,refine
from .spatial_bridges import endpoint,reconstruct
ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'data/reconstruction/word-v1-collection'

def prediction(a,b,report,exact_join=False,endpoint_policy=None,metadata=None):
    method=report['selected_method'];params=report['calibration']['parameters']
    sign=1 if b['x']>=a['x'] else -1
    from .endpoint_speed import orient,reconstruct as noise_reconstruct
    aa=orient(a,sign);bb=orient(b,sign)
    if min(aa['v'],bb['v'])<-.5 or bb['x']<aa['x']:return None
    p=baseline(aa,bb,'linear' if method=='M1_linear' else 'hermite')
    if method.startswith('kinematic_'):
        if endpoint_policy is not None and exact_join:
            r=noise_reconstruct(aa,bb,params,endpoint_policy,smoothness=float(method.split('_')[1]))
        else:
            r=refine(aa,bb,p,**params,smoothness=float(method.split('_')[1]),
                     position_tolerance=0. if exact_join else 1.,speed_tolerance=0. if exact_join else 1.)
        if metadata is not None:
            metadata.update(endpoint_policy=r.get('endpoint_policy','strict'),endpoint_corrections=r.get('endpoint_corrections',[]))
            if r.get('endpoint_corrections'):metadata['uncertainty']='not_calibrated_for_endpoint_correction'
        if r['state']!='candidate':return None
        p=r['points']
    acc=np.diff(p[:,2])/np.diff(p[:,0])
    if np.any(p[:,2]<-1e-5) or np.any(p[:,2]>params['vmax']+1e-5) or np.any(acc<params['amin']-1e-5) or np.any(acc>params['amax']+1e-5):return None
    if abs(p[0,2]-aa['v'])>1.00001 or abs(p[-1,2]-bb['v'])>1.00001:return None
    p[:,1]*=sign;return p.tolist()

def generate(snapshot,report,experimental_changed_ids=False,endpoint_policy=None,endpoint_excluded_sites=(),association_policy=None,association_distance_limit=350):
    if report.get('state')!='evaluated_ablation':raise ValueError('Completed held-out study required')
    local=[];between=[];rejected=defaultdict(int);endpoint_metadata={}
    def local_prediction(a,b,allow_correction=True):
        endpoint_metadata.clear()
        return prediction(a,b,report,exact_join=True,endpoint_policy=endpoint_policy if allow_correction and site['id'] not in endpoint_excluded_sites and 1.5<b['t']-a['t']<=90 else None,metadata=endpoint_metadata)
    for site in snapshot['sites']:
        groups=defaultdict(list)
        for tr in site['tracks']:
            if tr['class_type']=='2' and not tr.get('method'):groups[tuple(tr.get('source_key',[]))].append(tr)
        # The renderer omits intervals >1.5 s, whereas collection keeps a
        # clock/geometry-checked track intact up to 3 s. These holes live INSIDE
        # a fragment, so the between-fragment loop below could never find them.
        for tracks in groups.values():
            for tr in tracks:
                points=tr['points']
                for i in range(1,len(points)):
                    gap=points[i][0]-points[i-1][0]
                    if not 1.5<gap<=3:continue
                    a=endpoint(points[max(0,i-5):i],True)
                    b=endpoint(points[i:i+5],False)
                    if a is None or b is None:
                        rejected['short_local_insufficient_context']+=1;continue
                    p=local_prediction(a,b)
                    if p is None:
                        rejected['short_local_physical_rejection']+=1;continue
                    local.append(dict(**endpoint_metadata,site=site['id'],direction=tr['direction'],class_type='2',points=p,
                        source='inferred',method=report['selected_method'],identity='same_sensor_session_and_track',
                        gap_s=gap,gap_kind='internal_sampling_gap'))
        for candidate in site.get('local_gap_candidates',[]):
            if candidate['class_type']!='2':continue
            a,b=candidate['a'],candidate['b'];p=local_prediction(a,b)
            if p is None:rejected['local_physical_rejection']+=1;continue
            local.append(dict(**endpoint_metadata,site=site['id'],direction='eastbound' if b['x']>=a['x'] else 'westbound',class_type='2',points=p,
                source='inferred',method=report['selected_method'],identity='same_sensor_session_track_and_chain',gap_s=b['t']-a['t'],gap_kind='between_fragments'))
        # Backward compatibility for snapshots predating model-independent admission.
        if 'local_gap_candidates' in site:continue
        allowed={(round(p['points'][0][0],2),round(p['points'][-1][0],2)) for p in site.get('local_estimates',[]) if p['class_type']=='2'}
        for key,tracks in groups.items():
            if len(key)!=3:continue
            tracks.sort(key=lambda tr:tr['points'][0][0])
            for before,after in zip(tracks,tracks[1:]):
                if before['direction']!=after['direction']:continue
                a=endpoint(before['points'],True);b=endpoint(after['points'],False)
                if not a or not b or not 3<b['t']-a['t']<=30:continue
                if (round(a['t'],2),round(b['t'],2)) not in allowed:rejected['local_missing_2d_clock_support']+=1;continue
                p=local_prediction(a,b)
                if p is None:rejected['local_physical_rejection']+=1;continue
                local.append(dict(**endpoint_metadata,site=site['id'],direction=before['direction'],class_type='2',points=p,source='inferred',method=report['selected_method'],identity='same_sensor_session_and_track',gap_s=b['t']-a['t']))
    from .same_id_gaps import candidates as same_id_candidates
    for site in snapshot['sites']:
        for candidate in same_id_candidates(site):
            a,b=candidate['a'],candidate['b'];p=local_prediction(a,b,allow_correction=all(c=='2' for c in candidate['classes']))
            if any(q['site']==site['id'] and abs(q['points'][0][0]-a['t'])<.02 and abs(q['points'][-1][0]-b['t'])<.02 for q in local):continue
            if p is None:rejected['class_change_physical_rejection']+=1;continue
            local.append(dict(**endpoint_metadata,site=site['id'],direction=candidate['direction'],class_type=candidate['classes'][0],
                endpoint_classes=candidate['classes'],object_id=candidate['identity'][1],points=p,source='inferred',
                method='endpoint_tangent_constrained_kinematic',identity='same_sensor_session_id_recording_gap' if candidate['recording_gap'] else 'same_sensor_session_id_class_changed',
                gap_kind='recording_interruption' if candidate['recording_gap'] else 'classification_change',
                missing_receipt_fraction=candidate['missing_receipt_fraction'],gap_s=b['t']-a['t']))
    from .local_tracklet_matching import reconstruct as reconnect_local
    if experimental_changed_ids:
        for site in snapshot['sites']:
            reserved=[(round(p['points'][0][0],2),round(p['points'][-1][0],2)) for p in local if p['site']==site['id']]
            local.extend(reconnect_local(site,lambda a,b:prediction(a,b,report),reserved))
    # Existing movement-aware associations; do not create global vehicle identities.
    association_snapshot={**snapshot,'sites':[{**s,'tracks':[t for t in s['tracks'] if t['class_type']=='2']} for s in snapshot['sites']]}
    matcher=None
    if association_policy=='strict_physics_v1':
        from .matching_physics import associate as physical_associate
        matcher=lambda a,b:physical_associate(a,b,report['calibration']['parameters'],max_distance=association_distance_limit)
    associations=reconstruct(association_snapshot,association_method='feasible',matcher=matcher)
    by_id={s['id']:s for s in association_snapshot['sites']}
    for link in associations['links']:
        for path in link['paths']:
            a=endpoint(by_id[link['sites'][0]]['tracks'][path['upstream_fragment']]['points'],True)
            b=endpoint(by_id[link['sites'][1]]['tracks'][path['downstream_fragment']]['points'],False)
            p=prediction(a,b,report,exact_join=True)
            if p is None:rejected['between_physical_rejection']+=1;continue
            between.append(dict(sites=link['sites'],direction=link['direction'],class_type='2',points=p,source='inferred',method=report['selected_method'],identity='unverified_cross_sensor_association',association_cost=path['association_cost'],ambiguity_margin=path['ambiguity_margin']))
    return dict(state='ready',generated_at=time.time(),snapshot_generated_at=snapshot['generated_at'],start=snapshot['start'],end=snapshot['end'],expires_at=snapshot['start']+5400,
      endpoint_policy=endpoint_policy,endpoint_excluded_sites=list(endpoint_excluded_sites),endpoint_corrected_gaps=sum(bool(p.get('endpoint_corrections')) for p in local),
      method=report['selected_method'],association_method=association_policy or 'feasible_mutual_best',within_intersection=local,between_intersections=between,rejected=dict(rejected),
      association_diagnostics=[{k:v for k,v in link.items() if k!='paths'} | {'proposed_matches':len(link['paths'])} for link in associations['links']],
      comparison=report['test'],uncertainty=report['uncertainty'],
      limitations=['Selected local reconstruction ablation; not full Newell+CTM+signal model','Between-intersection accuracy and identities are unverified; applying local method across sensors is domain transfer','No inferred signal permissions or invented same-lane leaders','Validation uncertainty applies to prior local masked gaps only, not corrected endpoints or between sensors'])

def main(watch,region='florida',deadline=None):
    folder=FOLDER if region=='florida' else ROOT/'data/reconstruction/finch'
    folder.mkdir(parents=True,exist_ok=True);lock=open(folder/'layers.lock','w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);last=None
    while deadline is None or time.time()<deadline:
        try:
            status=json.loads((folder/'status.json').read_text())
            if status.get('state')=='evaluated_ablation':
                report=json.loads(Path(status['report']).read_text());snapshot=json.loads((ROOT/f'data/{region}-rolling/snapshot.json').read_text())
                if snapshot['start']>=time.time()-5400 and snapshot['generated_at']!=last:
                    policy_path=ROOT/'config/reconstruction/florida-endpoint-speed.json'
                    policy_config=json.loads(policy_path.read_text()) if policy_path.exists() else {}
                    association_path=ROOT/'config/reconstruction/florida-association.json'
                    association_policy=json.loads(association_path.read_text()).get('method') if association_path.exists() else None
                    if region=='finch':
                        model=json.loads((folder/'policy.json').read_text());policy_config={'parameters':model.get('endpoint_policy'),'excluded_sites':model.get('excluded_sites',[])};association_policy='strict_physics_v1'
                    result=generate(snapshot,report,association_distance_limit=350 if region=='florida' else report['calibration']['parameters']['vmax']*120,endpoint_policy=policy_config.get('parameters'),endpoint_excluded_sites=policy_config.get('excluded_sites',[]),association_policy=association_policy);temp=folder/'layers.tmp';temp.write_text(json.dumps(result,allow_nan=False));temp.replace(folder/'layers.json');last=snapshot['generated_at']
                    print(json.dumps({'state':'published','local':len(result['within_intersection']),'between':len(result['between_intersections'])}),flush=True)
        except (OSError,ValueError,KeyError) as exc:
            print(type(exc).__name__+': layers not published',flush=True)
        if not watch:return
        time.sleep(15)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--watch',action='store_true');p.add_argument('--region',choices=['florida','finch'],default='florida');p.add_argument('--deadline',type=float);a=p.parse_args();main(a.watch,a.region,a.deadline)
