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

def finch_endpoint_config(model,override=None):
    config={'parameters':model.get('endpoint_policy'),'excluded_sites':model.get('excluded_sites',[])}
    if not override:return config
    if override.get('version')!='stationary_noise_correction_v1' or override.get('parameters')!=config['parameters']:
        raise ValueError('Finch endpoint override differs from validated parameters')
    allowed=set(override.get('enabled_sites',[]))
    config['excluded_sites']=[site for site in config['excluded_sites'] if site not in allowed]
    return config

def prediction(a,b,report,exact_join=False,endpoint_policy=None,metadata=None,stationary_plateau=False,adaptive_grid=False):
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
        if r['state']!='candidate' and adaptive_grid and exact_join and method=='kinematic_0.01':
            from .adaptive_endpoint_grid import retry
            r,used=retry(aa,bb,params)
            if used and metadata is not None:
                metadata.update(estimation_model='endpoint_envelope_grid_retry_v1',exact_endpoint_interpolation=True)
        if r['state']!='candidate' and stationary_plateau and exact_join:
            from .stationary_plateau import estimate
            r=estimate(aa,bb,same_identity=True)
            if r['state']=='candidate' and metadata is not None:
                metadata.update(estimation_model=r['method'],exact_endpoint_interpolation=False,
                    endpoint_position_residual_m=[sign*v for v in r['endpoint_position_residual_m']],
                    observed_endpoint_speeds_mps=[sign*v for v in r['observed_endpoint_speeds_mps']],uncertainty=r['uncertainty'])
        if r['state']!='candidate':return None
        p=r['points']
    acc=np.diff(p[:,2])/np.diff(p[:,0])
    if np.any(p[:,2]<-1e-5) or np.any(p[:,2]>params['vmax']+1e-5) or np.any(acc<params['amin']-1e-5) or np.any(acc>params['amax']+1e-5):return None
    if abs(p[0,2]-aa['v'])>1.00001 or abs(p[-1,2]-bb['v'])>1.00001:return None
    p[:,1]*=sign;return p.tolist()

def generate(snapshot,report,experimental_changed_ids=False,endpoint_policy=None,endpoint_excluded_sites=(),association_policy=None,association_distance_limit=350,same_class_recovery=False,stationary_plateau=False,adaptive_grid=False,local_lateral=False,local_lateral_sites=(),terminal_chains=False,stationary_admission=False,instantaneous_boundary_policy=None,same_id_continuity=False):
    if report.get('state')!='evaluated_ablation':raise ValueError('Completed held-out study required')
    local=[];between=[];rejected=defaultdict(int);endpoint_metadata={}
    def local_prediction(a,b,allow_correction=True):
        endpoint_metadata.clear()
        return prediction(a,b,report,exact_join=True,endpoint_policy=endpoint_policy if allow_correction and site['id'] not in endpoint_excluded_sites and 1.5<b['t']-a['t']<=90 else None,metadata=endpoint_metadata,stationary_plateau=stationary_plateau and allow_correction and site['id'] not in endpoint_excluded_sites,adaptive_grid=adaptive_grid and allow_correction)
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
                    a=endpoint(points[:i],True)
                    b=endpoint(points[i:],False)
                    if a is None or b is None:
                        rejected['short_local_insufficient_context']+=1;continue
                    p=local_prediction(a,b)
                    if p is None:
                        rejected['short_local_physical_rejection']+=1;continue
                    local.append(dict(**endpoint_metadata,identity_key=list(tr.get('source_key',[])[:2]),site=site['id'],direction=tr['direction'],class_type='2',points=p,
                        source='inferred',method=report['selected_method'],identity='same_sensor_session_and_track',
                        gap_s=gap,gap_kind='internal_sampling_gap'))
        for candidate in site.get('local_gap_candidates',[]):
            if candidate['class_type']!='2':continue
            a,b=candidate['a'],candidate['b'];p=local_prediction(a,b)
            if p is None:rejected['local_physical_rejection']+=1;continue
            local.append(dict(**endpoint_metadata,identity_key=list(candidate.get('source_key',[])[:2]),site=site['id'],direction='eastbound' if b['x']>=a['x'] else 'westbound',class_type='2',points=p,
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
                local.append(dict(**endpoint_metadata,identity_key=list(key[:2]),site=site['id'],direction=before['direction'],class_type='2',points=p,source='inferred',method=report['selected_method'],identity='same_sensor_session_and_track',gap_s=b['t']-a['t']))
    from .same_id_gaps import candidates as same_id_candidates
    for site in snapshot['sites']:
        for candidate in same_id_candidates(site,include_same_class=same_class_recovery,allow_stationary_noise=stationary_admission and stationary_plateau and site['id'] not in endpoint_excluded_sites):
            a,b=candidate['a'],candidate['b']
            if candidate.get('stationary_noise_admission'):
                from .stationary_plateau import estimate
                quiet=estimate(a,b,same_identity=True)
                p=quiet['points'].tolist() if quiet['state']=='candidate' else None
                endpoint_metadata.clear()
                if p is not None:
                    endpoint_metadata.update({k:quiet[k] for k in ('endpoint_position_residual_m','observed_endpoint_speeds_mps','uncertainty','exact_endpoint_interpolation')})
                    endpoint_metadata.update(estimation_model=quiet['method'],stationary_noise_admission=True)
            else:p=local_prediction(a,b,allow_correction=all(c=='2' for c in candidate['classes']))
            if any(q['site']==site['id'] and q.get('identity_key')==list(candidate['identity']) and abs(q['points'][0][0]-a['t'])<.02 and abs(q['points'][-1][0]-b['t'])<.02 for q in local):continue
            if p is None:rejected['same_id_physical_rejection']+=1;continue
            local.append(dict(**endpoint_metadata,identity_key=list(candidate['identity']),site=site['id'],direction=candidate['direction'],class_type=candidate['classes'][0],
                frame_gap_basis=candidate['frame_gap_basis'],endpoint_classes=candidate['classes'],object_id=candidate['identity'][1],points=p,source='inferred',
                method='endpoint_tangent_constrained_kinematic',identity='same_sensor_session_id_recording_gap' if candidate['recording_gap'] else 'same_sensor_session_id_class_changed' if candidate['classification_changed'] else 'same_sensor_session_id',
                gap_kind='recording_interruption' if candidate['recording_gap'] else 'classification_change' if candidate['classification_changed'] else 'same_id_fragment_break',
                missing_receipt_fraction=candidate['missing_receipt_fraction'],gap_s=b['t']-a['t']))
    from .local_tracklet_matching import reconstruct as reconnect_local
    if experimental_changed_ids:
        for site in snapshot['sites']:
            reserved=[(round(p['points'][0][0],2),round(p['points'][-1][0],2)) for p in local if p['site']==site['id']]
            local.extend(reconnect_local(site,lambda a,b:prediction(a,b,report),reserved))
    if local_lateral:
        from .local_lateral_recovery import reconstruct as lateral_reconstruct
        def lateral_rejection(reason):rejected['lateral_'+reason]+=1
        for site in snapshot['sites']:
            if site['id'] not in local_lateral_sites:continue
            paths=lateral_reconstruct(site,lambda a,b:prediction(a,b,report,exact_join=True),audit=lateral_rejection)
            for p in paths:
                duplicate=any(q.get('site')==p['site'] and q.get('identity_key')==p['identity_key'] and abs(q['points'][0][0]-p['points'][0][0])<.02 and abs(q['points'][-1][0]-p['points'][-1][0])<.02 for q in local)
                if not duplicate:local.append(p)
    boundary_review=None
    if instantaneous_boundary_policy:
        from .instantaneous_boundary_layer import apply as apply_boundary_retry
        extra=apply_boundary_retry(snapshot,{'within_intersection':local},report,instantaneous_boundary_policy)
        local=extra['within_intersection'];boundary_review=extra['instantaneous_boundary_review']
    continuity_review=None
    if same_id_continuity:
        from .same_id_continuity import extend
        local,continuity_review=extend(snapshot,local)
    # The additional local links participate in terminal reservation below, so
    # their internal endpoints cannot also become between-sensor connections.
    # Existing movement-aware associations; do not create global vehicle identities.
    association_snapshot={**snapshot,'sites':[{**s,'tracks':[t for t in s['tracks'] if t['class_type']=='2']} for s in snapshot['sites']]}
    if terminal_chains:
        from .fragment_terminals import mark
        association_snapshot=mark(association_snapshot,local)
    matcher=None;endpoint_enricher=None
    if association_policy=='strict_physics_v1':
        from .matching_physics import associate as physical_associate
        matcher=lambda a,b:physical_associate(a,b,report['calibration']['parameters'],max_distance=association_distance_limit)
    elif association_policy in ('shape_partial_v1','shape_feasible_partial_v1'):
        from .shape_association import associate as shape_associate
        from .kinematic_gate import path as exact_gate
        gate=exact_gate if association_policy=='shape_feasible_partial_v1' else None
        matcher=lambda a,b:shape_associate(a,b,report['calibration']['parameters'],weight=.5,max_distance=association_distance_limit,path_gate=gate)
    elif association_policy=='bidirectional_shape_v1':
        from .bidirectional_association import associate as bidirectional_associate,motion_context
        matcher=lambda a,b:bidirectional_associate(a,b,report['calibration']['parameters'],blend=.5,max_distance=association_distance_limit)
        endpoint_enricher=lambda ep,tr,is_exit:dict(ep,motion_context=motion_context(tr['points'],is_exit))
    associations=reconstruct(association_snapshot,association_method='feasible',matcher=matcher,endpoint_enricher=endpoint_enricher)
    by_id={s['id']:s for s in association_snapshot['sites']}
    from .trajectory_provenance import fragment_index,link_references
    source_index=fragment_index(snapshot)
    for link in associations['links']:
        for path in link['paths']:
            a=endpoint(by_id[link['sites'][0]]['tracks'][path['upstream_fragment']]['points'],True)
            b=endpoint(by_id[link['sites'][1]]['tracks'][path['downstream_fragment']]['points'],False)
            p=prediction(a,b,report,exact_join=True)
            if p is None:rejected['between_physical_rejection']+=1;continue
            between.append(dict(sites=link['sites'],direction=link['direction'],class_type='2',points=p,source='inferred',method=report['selected_method'],identity='unverified_cross_sensor_association',association_cost=path['association_cost'],ambiguity_margin=path['ambiguity_margin'],shape_evidence=path.get('shape_evidence'),endpoint_provenance=link_references(link['sites'][0],link['sites'][1],by_id[link['sites'][0]]['tracks'][path['upstream_fragment']],by_id[link['sites'][1]]['tracks'][path['downstream_fragment']],source_index)))
    return dict(state='ready',moderate_timing_sites=snapshot.get('moderate_timing_sites',[]),transform_manifest=snapshot.get('transform_manifest'),time_basis=snapshot.get('time_basis','receipt'),generated_at=time.time(),snapshot_generated_at=snapshot['generated_at'],start=snapshot['start'],end=snapshot['end'],expires_at=snapshot['start']+5400,
      stationary_admission=stationary_admission,terminal_chains=terminal_chains,local_lateral=local_lateral,local_lateral_sites=list(local_lateral_sites),same_class_recovery=same_class_recovery,stationary_plateau=stationary_plateau,adaptive_grid=adaptive_grid,endpoint_policy=endpoint_policy,endpoint_excluded_sites=list(endpoint_excluded_sites),endpoint_corrected_gaps=sum(bool(p.get('endpoint_corrections')) for p in local),
      method=report['selected_method'],association_method=association_policy or 'feasible_mutual_best',within_intersection=local,between_intersections=between,rejected=dict(rejected),instantaneous_boundary_review=boundary_review,same_id_continuity=continuity_review,
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
                        model=json.loads((folder/'policy.json').read_text())
                        override_path=ROOT/'config/reconstruction/finch-endpoint-speed.json'
                        override=json.loads(override_path.read_text()) if override_path.exists() else None
                        policy_config=finch_endpoint_config(model,override);association_policy='strict_physics_v1'
                    shape_path=ROOT/'config/reconstruction/corridor-shape-policy.json'
                    if shape_path.exists():
                        shape_policy=json.loads(shape_path.read_text())
                        if region in shape_policy.get('enabled_regions',[]) and shape_policy.get('method') in ('shape_partial_v1','shape_feasible_partial_v1') and shape_policy.get('weight')==.5:association_policy=shape_policy['method']
                    bidirectional_path=ROOT/'config/reconstruction/florida-bidirectional.json'
                    if region=='florida' and bidirectional_path.exists():
                        bidirectional=json.loads(bidirectional_path.read_text())
                        if bidirectional.get('enabled') and bidirectional.get('blend')==.5:association_policy='bidirectional_shape_v1'
                    recovery_path=ROOT/'config/reconstruction/same-class-recovery.json'
                    recovery=json.loads(recovery_path.read_text()) if recovery_path.exists() else {}
                    plateau_path=ROOT/'config/reconstruction/stationary-plateau.json'
                    plateau=json.loads(plateau_path.read_text()) if plateau_path.exists() else {}
                    plateau_enabled=plateau.get('method')=='bounded_stationary_latent_position' and region in plateau.get('enabled_regions',[])
                    grid_path=ROOT/'config/reconstruction/adaptive-grid.json'
                    grid_policy=json.loads(grid_path.read_text()) if grid_path.exists() else {}
                    grid_enabled=grid_policy.get('method')=='endpoint_envelope_grid_retry_v1' and region in grid_policy.get('enabled_regions',[])
                    local_lateral_path=ROOT/'config/reconstruction/florida-local-lateral.json'
                    local_lateral_config=json.loads(local_lateral_path.read_text()) if local_lateral_path.exists() else {}
                    local_lateral_enabled=region=='florida' and local_lateral_config.get('enabled',False) and local_lateral_config.get('max_gap_s')==10
                    gap_path=ROOT/'config/reconstruction/florida-gap-integrity.json'
                    gap_policy=json.loads(gap_path.read_text()) if gap_path.exists() and region=='florida' else {}
                    boundary_path=ROOT/'config/reconstruction/florida-instantaneous-boundary.json'
                    boundary_policy=json.loads(boundary_path.read_text()) if region=='florida' and boundary_path.exists() else None
                    simple_path=ROOT/'config/reconstruction/florida-color-slope.json'
                    simple=json.loads(simple_path.read_text()) if simple_path.exists() else {}
                    if region=='florida' and simple.get('enabled'):
                        from .color_slope import generate as color_generate
                        result=color_generate(snapshot)
                        validation_path=ROOT/'data/reconstruction/color-slope/validation.json'
                        if validation_path.exists():
                            validation=json.loads(validation_path.read_text())
                            result['color_validation']={k:validation[k] for k in ('summary','association','limitations','snapshot_sha256')}
                    else:
                        result=generate(snapshot,report,same_id_continuity=region=='florida',terminal_chains=gap_policy.get('terminal_chains',False),stationary_admission=gap_policy.get('stationary_admission',False),local_lateral=local_lateral_enabled,local_lateral_sites=local_lateral_config.get('enabled_sites',[]),adaptive_grid=grid_enabled,stationary_plateau=plateau_enabled,same_class_recovery=region in recovery.get('enabled_regions',[]),association_distance_limit=350 if region=='florida' else report['calibration']['parameters']['vmax']*120,endpoint_policy=policy_config.get('parameters'),endpoint_excluded_sites=policy_config.get('excluded_sites',[]),association_policy=association_policy,instantaneous_boundary_policy=boundary_policy)
                    residual_path=ROOT/'config/reconstruction/florida-residual-color.json'
                    if region=='florida' and residual_path.exists() and json.loads(residual_path.read_text()).get('enabled'):
                        from .residual_color_slope import generate as residual_generate
                        result['residual_color']=residual_generate(snapshot,result)
                        evidence_path=ROOT/'data/reconstruction/residual-color-review/report.json'
                        if evidence_path.exists():result['residual_color']['validation']=json.loads(evidence_path.read_text())
                    if region=='florida':
                        from .local_group_prior import apply as apply_group_prior
                        group_policy_path=ROOT/'data/reconstruction/trajectory-group-local-review/review-002/policy.json'
                        group_policy=json.loads(group_policy_path.read_text()) if group_policy_path.exists() else None
                        result=apply_group_prior(snapshot,result,group_policy,report['calibration']['parameters'])
                        from .trajectory_group_layer import build as build_groups
                        result['trajectory_groups']=build_groups(snapshot,result,report)
                        from .coverage_audit import audit as audit_coverage
                        result['coverage_audit']=audit_coverage(snapshot,result)
                        from .between_coverage_audit import audit as audit_overlap
                        overlap=audit_overlap(snapshot,result)
                        result['coverage_audit']['overlap_links']=[{k:v for k,v in link.items() if k!='hypotheses'} for link in overlap['links']]
                    temp=folder/'layers.tmp';temp.write_text(json.dumps(result,allow_nan=False));temp.replace(folder/'layers.json');last=snapshot['generated_at']
                    print(json.dumps({'state':'published','local':len(result['within_intersection']),'between':len(result['between_intersections'])}),flush=True)
        except (OSError,ValueError,KeyError) as exc:
            print(type(exc).__name__+': layers not published',flush=True)
        if not watch:return
        time.sleep(15)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--watch',action='store_true');p.add_argument('--region',choices=['florida','finch'],default='florida');p.add_argument('--deadline',type=float);a=p.parse_args();main(a.watch,a.region,a.deadline)
