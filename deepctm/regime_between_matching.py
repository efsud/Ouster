"""Experimental between-view timing priors from endpoint-local motion groups.

Groups summarize observed local regimes. Matching two groups is not a vehicle-ID
join. This adapter retains the existing three-other-anchor, physical, ambiguity,
movement and one-to-one gates. A new frozen policy is required for publication.
"""
from dataclasses import asdict

from .between_group_matching import associate as _associate
from .trajectory_regime_groups import RegimeConfig, VERSION as GROUPING_VERSION

VERSION = 'endpoint_regime_group_anchor_v1'


def endpoint_group(endpoint, assignments):
    """Use only a unique group covering the endpoint's observed sample.

    No nearest-time extrapolation through a gap and no whole-track majority vote.
    At a boundary belonging to two different regime groups we abstain.
    """
    time = float(endpoint['t'])
    candidates = {str(member['group_id']) for member in assignments
                  if member['start_s'] - 1e-6 <= time <= member['end_s'] + 1e-6
                  and member.get('regime') != 'stopped'}
    return next(iter(candidates)) if len(candidates) == 1 else None


def annotate_endpoints(endpoints, site, grouped):
    assignments = grouped.get('assignments', [])
    if len(assignments) != len(site['tracks']):
        raise ValueError('Regime assignments must index the exact original snapshot')
    result = []
    for ep in endpoints:
        i = ep['fragment']; track = site['tracks'][i]
        key = track.get('source_key', [])
        local_id = (site['id'], str(key[0]), str(key[1])) if len(key) >= 2 else None
        result.append(dict(ep, trajectory_group=endpoint_group(ep, assignments[i]),
                           local_identity=local_id))
    return result


def associate(left, right, params, weight=.25, **kwargs):
    """Reuse established association gates; only endpoint group labels differ."""
    matches = _associate(left, right, params, weight=weight, **kwargs)
    return [dict(m, method=VERSION,
                 grouping='endpoint_local_observed_motion_regimes',
                 cross_sensor_identity_verified=False)
            if m.get('group_assistance') else m for m in matches]


def qualified(policy, parameters):
    return bool(policy and policy.get('enabled') and
                policy.get('version') == VERSION and
                policy.get('validation_state') == 'complete' and
                policy.get('parameters') == parameters and
                policy.get('grouping_version') == GROUPING_VERSION and
                policy.get('grouping_config') == asdict(RegimeConfig()) and
                policy.get('weight') == .25)


def build_additional(snapshot, report, existing_layers, grouped_sites,
                     policy=None, max_distance=350):
    """Publish only policy-qualified, disjoint additional hypotheses.

    The old whole-track grouping policy cannot enable this new method. Existing
    observations and estimates are untouched and all occupied ends are reserved.
    """
    params = report['calibration']['parameters']
    if not qualified(policy, params):
        return dict(paths=[], diagnostics=[], status='new_regime_policy_not_qualified')
    from .fragment_terminals import mark
    from .trajectory_provenance import signature, fragment_index, link_references
    from .spatial_bridges import reconstruct
    from .reconstruction_layers import prediction
    from .bidirectional_association import motion_context

    source_index = fragment_index(snapshot)
    groups_by_id = {s['id']: s for s in grouped_sites}
    memberships = {}
    for site in snapshot['sites']:
        assignment = groups_by_id.get(site['id'], {}).get('assignments', [])
        if len(assignment) != len(site['tracks']):
            raise ValueError('Regime assignments must index the exact original snapshot')
        for i, tr in enumerate(site['tracks']):
            memberships[site['id'], signature(tr)] = assignment[i]
    prepared = dict(snapshot, sites=[dict(s, tracks=[t for t in s['tracks']
                                                    if t['class_type'] == '2'])
                                    for s in snapshot['sites']])
    containers = [existing_layers, existing_layers.get('residual_color') or {},
                  existing_layers.get('trajectory_groups') or {},
                  existing_layers.get('regime_groups') or {}]
    prior_local = [p for c in containers for p in c.get('within_intersection', [])]
    prior_between = [p for c in containers for p in c.get('between_intersections', [])]
    prepared = mark(prepared, prior_local)
    sites = {s['id']: s for s in prepared['sites']}
    reserved_a = set(); reserved_b = set(); reserved_points_a = set(); reserved_points_b = set()

    def point_key(site, point):
        return site, round(point[0], 2), round(point[1], 2)

    for p in prior_local:
        if p.get('site') and len(p.get('points', [])) >= 2:
            reserved_points_a.add(point_key(p['site'], p['points'][0]))
            reserved_points_b.add(point_key(p['site'], p['points'][-1]))
    for p in prior_between:
        provenance = p.get('endpoint_provenance') or {}
        for role, reserved in [('departure', reserved_a), ('arrival', reserved_b)]:
            if provenance.get(role, {}).get('fragment_id'):
                reserved.add(provenance[role]['fragment_id'])
        if len(p.get('points', [])) >= 2 and len(p.get('sites', [])) == 2:
            reserved_points_a.add(point_key(p['sites'][0], p['points'][0]))
            reserved_points_b.add(point_key(p['sites'][1], p['points'][-1]))
    audits = []; retained = {}

    def attach(endpoints):
        output = []
        for ep in endpoints:
            tr = sites[ep['site']]['tracks'][ep['fragment']]
            key = tr.get('source_key', [])
            output.append(dict(ep, trajectory_group=endpoint_group(
                ep, memberships[ep['site'], signature(tr)]),
                local_identity=(ep['site'], str(key[0]), str(key[1])) if len(key) >= 2 else None))
        return output

    def matcher(left, right):
        aa, bb = attach(left), attach(right); diag = {}
        matches = associate(aa, bb, params, diagnostics=diag, max_distance=max_distance)
        extras = []
        for match in matches:
            if not match.get('group_assistance'):
                continue
            a, b = left[match['left']], right[match['right']]
            at = sites[a['site']]['tracks'][a['fragment']]
            bt = sites[b['site']]['tracks'][b['fragment']]
            refs = link_references(a['site'], b['site'], at, bt, source_index)
            occupied = (refs['departure']['fragment_id'] in reserved_a or
                        refs['arrival']['fragment_id'] in reserved_b or
                        point_key(a['site'], at['points'][-1]) in reserved_points_a or
                        point_key(b['site'], bt['points'][0]) in reserved_points_b)
            if occupied:
                diag['existing_endpoint_reserved'] = diag.get('existing_endpoint_reserved', 0) + 1
                continue
            points = prediction(a, b, report, exact_join=True)
            if points is None:
                diag['final_path_rejected'] = diag.get('final_path_rejected', 0) + 1
                continue
            retained[a['site'], a['fragment'], b['site'], b['fragment']] = dict(
                points=points, endpoint_provenance=refs, group_evidence=match['group_evidence'],
                departure_group=aa[match['left']]['trajectory_group'],
                arrival_group=bb[match['right']]['trajectory_group'])
            extras.append(match)
        audits.append(dict(sites=[left[0]['site'], right[0]['site']] if left and right else [],
                           **diag, additional_paths=len(extras)))
        return extras

    associations = reconstruct(prepared, matcher=matcher,
        endpoint_enricher=lambda ep, tr, side: dict(ep, motion_context=motion_context(tr['points'], side)))
    paths = []
    for link in associations['links']:
        for p in link['paths']:
            key = link['sites'][0], p['upstream_fragment'], link['sites'][1], p['downstream_fragment']
            paths.append(dict(retained[key], sites=link['sites'], direction=link['direction'],
                class_type='2', source='inferred', method=VERSION,
                identity='unverified_cross_sensor_association', estimated=True, experimental=True,
                cross_sensor_identity_verified=False, association_cost=p['association_cost'],
                ambiguity_margin=p['ambiguity_margin']))
    return dict(paths=paths, diagnostics=audits, status='qualified_spatial_proxy_only',
                limitations=['Endpoint regime groups are local observed similarity labels, not vehicle identity joins.',
                             'Actual cross-sensor vehicle identities and clock offsets remain unverified.'])
