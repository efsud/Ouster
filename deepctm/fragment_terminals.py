"""Exclude internal chain endpoints from cross-site departure/arrival searches.

Only already accepted same-session/object local bridges supply continuity.
No estimated samples enter endpoint speed fits or replace measured positions.
"""
from collections import defaultdict


def mark(snapshot, local_paths):
    links = defaultdict(list)
    for path in local_paths:
        key = path.get('identity_key')
        points = path.get('points', [])
        if (not key or len(key) != 2 or len(points) < 2
                or not path.get('identity', '').startswith('same_sensor_session')
                or points[-1][0] <= points[0][0]):
            continue
        links[path['site'], tuple(key)].append((points[0], points[-1]))
    sites = []
    for site in snapshot['sites']:
        tracks = []
        by_identity = defaultdict(list)
        for i, tr in enumerate(site['tracks']):
            by_identity[tuple(tr.get('source_key', [])[:2])].append(i)
        blocked = defaultdict(set)
        for key, indices in by_identity.items():
            for a, b in links.get((site['id'], key), []):
                left = [i for i in indices if coincident(site['tracks'][i]['points'][-1], a)]
                right = [i for i in indices if coincident(site['tracks'][i]['points'][0], b)]
                # Ambiguous duplicate fragments are not sufficient evidence.
                if len(left) == len(right) == 1 and left[0] != right[0]:
                    blocked[left[0]].add('departure')
                    blocked[right[0]].add('arrival')
        for i, tr in enumerate(site['tracks']):
            tracks.append(dict(tr, internal_chain_endpoints=sorted(blocked[i])))
        sites.append(dict(site, tracks=tracks))
    return dict(snapshot, sites=sites)


def coincident(observed, inferred):
    return abs(observed[0]-inferred[0]) < .02 and abs(observed[1]-inferred[1]) <= .051
