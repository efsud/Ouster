"""Experimental individual association with independently clustered flow evidence.

Group IDs are LOCAL labels, never cross-sensor vehicle identities. The baseline
assignments are hypotheses too. Three other baseline pairs are required before a
cohort supplies a timing prior. Existing accepted matches are retained; only
unoccupied endpoint pairs with a global ambiguity margin may be added.
"""
from collections import Counter
import numpy as np
from .bidirectional_association import associate as baseline_associate, two_sided_cost
from .spatial_bridges import pair_cost
from .matching_physics import reachability
from .kinematic_gate import path
from .object_shape import discrepancy
from .global_association import solve_edges

VERSION = 'trajectory_group_anchor_v1'


def _expected(a, b):
    return abs(b['x'] - a['x']) / max(1., (abs(a['v']) + abs(b['v'])) / 2)


def timing_prior(a, b, left, right, anchors, minimum=3):
    """Leave both candidate endpoints out of independently paired group evidence."""
    ga, gb = a.get('trajectory_group'), b.get('trajectory_group')
    if ga is None or gb is None:
        return None
    rows = []; seen_a=set(); seen_b=set()
    for m in sorted(anchors,key=lambda m:m.get('cost',0)):
        aa, bb = left[m['left']], right[m['right']]
        if aa is a or bb is b or (a.get('local_identity') is not None and aa.get('local_identity')==a['local_identity']) or (b.get('local_identity') is not None and bb.get('local_identity')==b['local_identity']):
            continue
        if aa.get('trajectory_group') != ga or bb.get('trajectory_group') != gb:
            continue
        # Distinct local identities are necessary; the labels never cross sides.
        if aa.get('local_identity') is None or bb.get('local_identity') is None:
            continue
        if aa['local_identity'] in seen_a or bb['local_identity'] in seen_b:
            continue
        seen_a.add(aa['local_identity']); seen_b.add(bb['local_identity'])
        rows.append((aa, bb, bb['t']-aa['t']-_expected(aa, bb)))
    if len({r[0]['local_identity'] for r in rows}) < minimum or len({r[1]['local_identity'] for r in rows}) < minimum:
        return None
    residuals = np.asarray([r[2] for r in rows], float)
    center = float(np.median(residuals))
    mad = float(np.median(abs(residuals-center)))
    if mad > 2.:
        return None
    scale = max(.5, 1.4826*mad)
    observed = b['t']-a['t']-_expected(a, b)
    return dict(anchor_count=len(rows), timing_residual_s=float(observed-center),
                anchor_delay_median_s=center, anchor_delay_mad_s=mad,
                penalty=min(3., abs(observed-center)/scale),
                interpretation='group_flow_timing_prior_not_individual_identity')


def associate(left, right, params, weight=.25, threshold=1.5, margin=.25,
              max_distance=350, diagnostics=None):
    """Retain fixed .5-blend baseline; consider cohort-corroborated extras only.

    All alternative feasible assignments remain visible, including baseline-used
    endpoints. We never remove competitors to manufacture extra certainty.
    """
    baseline = baseline_associate(left, right, params, blend=.5,
                                  threshold=threshold, margin=margin,
                                  max_distance=max_distance)
    if not weight:
        return baseline
    anchors = [m for m in baseline if m['margin'] >= .5 and m['cost'] <= .75]
    edges, paths, priors, shapes = {}, {}, {}, {}
    counts = Counter(baseline_matches=len(baseline), anchor_matches=len(anchors))
    for i, a in enumerate(left):
        for j, b in enumerate(right):
            score = pair_cost(a, b, max_distance)
            if score is None:
                continue
            motion = two_sided_cost(a, b, params)
            if motion is not None:
                score = .5*score+.5*motion
            if score >= threshold or reachability(a, b, params):
                continue
            points = path(a, b, params)
            if points is None:
                continue
            shape = discrepancy(a.get('shape'), b.get('shape'))
            score += .5*shape if shape is not None else 0
            if score >= threshold:
                continue
            prior = timing_prior(a, b, left, right, anchors)
            # Nonnegative penalty only: group evidence cannot make a physically
            # weak edge appear cheaper than its original endpoint evidence.
            cost = score + weight*prior['penalty'] if prior else score
            if cost >= threshold:
                continue
            key = i, j
            edges[key], paths[key], shapes[key] = cost, points, shape
            if prior:
                priors[key] = prior
    selected = solve_edges(len(left), len(right), edges, unmatched_cost=threshold/2, margin=margin)
    used_a = {m['left'] for m in baseline}; used_b = {m['right'] for m in baseline}
    result = [dict(m, group_assistance=False) for m in baseline]
    for m in selected:
        key = m['left'], m['right']
        if key not in priors or m['left'] in used_a or m['right'] in used_b:
            continue
        result.append(dict(m, points=paths[key], group_assistance=True,
                           group_evidence=priors[key], method=VERSION,
                           cross_sensor_identity_verified=False))
        used_a.add(m['left']); used_b.add(m['right'])
    counts.update(eligible_group_edges=len(priors), added_matches=len(result)-len(baseline),
                  assigned_pairs=len(result), feasible_edges=len(edges))
    if diagnostics is not None:
        diagnostics.update(counts)
    return result


def annotate_endpoints(endpoints, site, grouped):
    """Attach LOCAL group and namespace evidence without assuming ID transfer."""
    assignments = grouped['assignments']
    result = []
    for ep in endpoints:
        i = ep['fragment']; tr = site['tracks'][i]
        key = tr.get('source_key', [])
        identity = (site['id'], str(key[0]), str(key[1])) if len(key) >= 2 else None
        result.append(dict(ep, trajectory_group=assignments[i], local_identity=identity))
    return result


def build_additional(snapshot, report, existing_layers, grouped_sites, max_distance=350):
    """Produce an OPTIONAL additional layer, preserving every existing estimate.

    ``grouped_sites`` is the list returned by trajectory_group_layer.build.
    Indices refer to the original snapshot. Reuse production movement filters,
    coverage-edge filters and accepted-local-chain endpoint suppression.
    """
    from .fragment_terminals import mark
    from .trajectory_provenance import signature, fragment_index, link_references
    from .spatial_bridges import reconstruct
    from .reconstruction_layers import prediction
    from .bidirectional_association import motion_context
    source_index=fragment_index(snapshot)
    groups_by_id={s['id']:s for s in grouped_sites}
    memberships={}
    for site in snapshot['sites']:
        groups=groups_by_id.get(site['id'],{})
        assignment=groups.get('assignments',[])
        if len(assignment)!=len(site['tracks']):
            raise ValueError('Group assignments must index the exact original snapshot')
        for i,tr in enumerate(site['tracks']):
            memberships[site['id'],signature(tr)]=assignment[i]
    prepared=dict(snapshot,sites=[dict(s,tracks=[t for t in s['tracks'] if t['class_type']=='2']) for s in snapshot['sites']])
    containers=[existing_layers,existing_layers.get('residual_color') or {},existing_layers.get('trajectory_groups') or {}]
    prior_local=[p for container in containers for p in container.get('within_intersection',[])]
    prior_between=[p for container in containers for p in container.get('between_intersections',[])]
    prepared=mark(prepared,prior_local)
    sites={s['id']:s for s in prepared['sites']}
    reserved_a=set();reserved_b=set();reserved_points_a=set();reserved_points_b=set()
    def point_key(site,point):return site,round(point[0],2),round(point[1],2)
    for p in prior_local:
        if p.get('site') and len(p.get('points',[]))>=2:
            reserved_points_a.add(point_key(p['site'],p['points'][0]))
            reserved_points_b.add(point_key(p['site'],p['points'][-1]))
    for p in prior_between:
        provenance=p.get('endpoint_provenance') or {}
        for role,reserved in [('departure',reserved_a),('arrival',reserved_b)]:
            if provenance.get(role,{}).get('fragment_id'):
                reserved.add(provenance[role]['fragment_id'])
        if len(p.get('points',[]))>=2 and len(p.get('sites',[]))==2:
            reserved_points_a.add(point_key(p['sites'][0],p['points'][0]))
            reserved_points_b.add(point_key(p['sites'][1],p['points'][-1]))
    audits=[];retained={}
    def attach(endpoints):
        output=[]
        for ep in endpoints:
            tr=sites[ep['site']]['tracks'][ep['fragment']]
            key=tr.get('source_key',[])
            output.append(dict(ep,trajectory_group=memberships[ep['site'],signature(tr)],
                               local_identity=(ep['site'],str(key[0]),str(key[1])) if len(key)>=2 else None))
        return output
    def matcher(left,right):
        aa,bb=attach(left),attach(right);diag={}
        matches=associate(aa,bb,report['calibration']['parameters'],diagnostics=diag,max_distance=max_distance)
        extras=[]
        for m in matches:
            if not m.get('group_assistance'):continue
            a,b=left[m['left']],right[m['right']]
            at=sites[a['site']]['tracks'][a['fragment']];bt=sites[b['site']]['tracks'][b['fragment']]
            refs=link_references(a['site'],b['site'],at,bt,source_index)
            if refs['departure']['fragment_id'] in reserved_a or refs['arrival']['fragment_id'] in reserved_b:
                diag['existing_endpoint_reserved']=diag.get('existing_endpoint_reserved',0)+1;continue
            if point_key(a['site'],at['points'][-1]) in reserved_points_a or point_key(b['site'],bt['points'][0]) in reserved_points_b:
                diag['existing_endpoint_reserved']=diag.get('existing_endpoint_reserved',0)+1;continue
            p=prediction(a,b,report,exact_join=True)
            if p is None:
                diag['final_path_rejected']=diag.get('final_path_rejected',0)+1;continue
            retained[a['site'],a['fragment'],b['site'],b['fragment']]=dict(points=p,
                    endpoint_provenance=refs,group_evidence=m['group_evidence'],
                    departure_group=aa[m['left']]['trajectory_group'],arrival_group=bb[m['right']]['trajectory_group'])
            extras.append(m)
        audits.append(dict(sites=[left[0]['site'],right[0]['site']] if left and right else [],
                           **diag,additional_paths=len(extras)))
        return extras
    associations=reconstruct(prepared,matcher=matcher,
              endpoint_enricher=lambda ep,tr,side:dict(ep,motion_context=motion_context(tr['points'],side)))
    paths=[]
    for link in associations['links']:
        for path_ in link['paths']:
            key=link['sites'][0],path_['upstream_fragment'],link['sites'][1],path_['downstream_fragment']
            paths.append(dict(retained[key],sites=link['sites'],direction=link['direction'],class_type='2',
                              source='inferred',method=VERSION,identity='unverified_cross_sensor_association',
                              estimated=True,experimental=True,cross_sensor_identity_verified=False,
                              association_cost=path_['association_cost'],ambiguity_margin=path_['ambiguity_margin']))
    return dict(paths=paths,diagnostics=audits,status='qualified_spatial_proxy_only',
                limitations=['Group flow support does not establish a shared individual vehicle identity between sensors.',
                             'Only additional disjoint hypotheses are returned; current observations and estimates stay unchanged.'])
