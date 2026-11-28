"""Account for observable gaps; never turn unmatched fragments into vehicle counts."""
from collections import Counter, defaultdict
from .local_gaps import VEHICLES
from .same_id_gaps import candidates


def audit(snapshot, layers):
    local = layers.get('within_intersection', [])
    extra = layers.get('residual_color', {})
    sites = []
    for site in snapshot['sites']:
        paths = [p for p in local if p['site'] == site['id']]
        experiments = [p for p in extra.get('within_intersection', []) if p['site'] == site['id']]
        groups = defaultdict(list)
        reasons = {}
        def record(row):
            reasons[tuple(row['identity']), round(row['start'], 3), round(row['end'], 3)] = row['reason']
        list(candidates(site, include_same_class=True, audit=record,
                        allow_stationary_noise=site['id'] not in layers.get('endpoint_excluded_sites', [])))
        gaps = []
        roles = Counter()
        for tr in site['tracks']:
            if tr.get('method') or tr['class_type'] not in VEHICLES or not tr['points']:
                continue
            roles[tr.get('movement', {}).get('role', 'unknown')] += 1
            key = tuple(tr.get('source_key', [])[:2])
            if len(key) != 2:
                continue
            groups[key].append(tr)
            for a, b in zip(tr['points'], tr['points'][1:]):
                if b[0] - a[0] > 1.5:
                    gaps.append((key, a, b, 'internal_sampling_gap'))
        for key, tracks in groups.items():
            tracks.sort(key=lambda tr: tr['points'][0][0])
            for before, after in zip(tracks, tracks[1:]):
                a, b = before['points'][-1], after['points'][0]
                if b[0] - a[0] <= 1.5:
                    continue
                reason = reasons.get((key, round(a[0], 3), round(b[0], 3)), 'not_admitted')
                gaps.append((key, a, b, reason))
        def joined(key, a, b, population):
            for p in population:
                identity = p.get('identity_key')
                if not identity or tuple(identity) != key:
                    continue
                u, v = p['points'][0], p['points'][-1]
                if abs(a[0]-u[0]) < .02 and abs(b[0]-v[0]) < .02 and abs(a[1]-u[1]) <= .051 and abs(b[1]-v[1]) <= .051:
                    return True
            return False
        counts = Counter(); unresolved = Counter(); seconds = Counter()
        for key, a, b, reason in gaps:
            state = 'baseline_estimated' if joined(key,a,b,paths) else 'experimental_estimated' if joined(key,a,b,experiments) else 'unresolved'
            counts[state] += 1; seconds[state] += b[0]-a[0]
            if state == 'unresolved':
                unresolved['motion_model_rejected' if reason == 'candidate' else reason] += 1
        sites.append(dict(site=site['id'], name=site['name'], observable_same_id_gaps=len(gaps),
            baseline_estimated=counts['baseline_estimated'], experimental_estimated=counts['experimental_estimated'],
            unresolved=counts['unresolved'], unresolved_reasons=dict(unresolved), gap_seconds=dict(seconds),
            all_baseline_local_paths=len(paths), all_experimental_local_paths=len(experiments),
            vehicle_fragments=sum(roles.values()), movement_roles=dict(roles)))
    links = []
    for link in layers.get('association_diagnostics', []):
        matched = sum(p['sites']==link['sites'] and p['direction']==link['direction'] for p in layers.get('between_intersections', []))
        experimental = sum(p['sites']==link['sites'] and p['direction']==link['direction'] for p in extra.get('between_intersections', []))
        links.append(dict(sites=link['sites'],names=link['names'],direction=link['direction'],
            eligible_departures=link['departure_candidates'],eligible_arrivals=link['arrival_candidates'],
            baseline_estimated=matched, experimental_estimated=experimental,
            baseline_unmatched_departures=max(0,link['departure_candidates']-matched),
            baseline_unmatched_arrivals=max(0,link['arrival_candidates']-matched),
            exclusions=link.get('diagnostics',[])))
    return dict(snapshot_generated_at=snapshot['generated_at'],sites=sites,links=links,
        kpi_policy={'observations':'eligible for observation-based KPIs subject to input quality checks',
                    'estimated_paths':'excluded from measured KPI inputs',
                    'cross_sensor_travel_time':'not identity-validated; experimental only'},
        limitations=['Gap counts cover observed same-session/object endpoints, not completely unseen vehicles or changed IDs.',
                     'Same IDs may be reused; timing and motion gates still apply.',
                     'Movement roles and corridor exits are geometry-based estimates, not verified unique vehicle counts.',
                     'Link unmatched counts describe the baseline candidate pool; experimental additions may use a different class pool.',
                     'A connected figure does not establish KPI accuracy.'])
