"""Trace inferred links to measured, site-local fragments without global IDs."""
from collections import defaultdict
import hashlib
import json


def signature(track):
    points = track['points']
    return (tuple(track.get('source_key', [])), track.get('class_type'),
            track.get('direction'), tuple(points[0]), tuple(points[-1]), len(points))


def fragment_index(snapshot):
    index = defaultdict(list)
    for site in snapshot['sites']:
        for number, track in enumerate(site['tracks']):
            if track.get('points'):
                index[site['id'], signature(track)].append(number)
    return index


def endpoint_reference(site_id, track, exit_side, index):
    """Indices refer to the original snapshot, including all object classes.

    Copied/filtered tracks retain their reference. Identical duplicated records
    report every source index rather than silently asserting unique evidence.
    """
    sig = signature(track)
    encoded = json.dumps([site_id, sig], separators=(',', ':'), allow_nan=False)
    point = track['points'][-1 if exit_side else 0]
    return {
        'site': site_id,
        'fragment_id': hashlib.sha256(encoded.encode()).hexdigest()[:24],
        'source_fragment_indices': index.get((site_id, sig), []),
        'source_key': list(track.get('source_key', [])),
        'identity_scope': 'sensor_session_object_only',
        'class_type': track.get('class_type'),
        'direction': track.get('direction'),
        'observed_endpoint': list(point),
        'fragment_start': track['points'][0][0],
        'fragment_end': track['points'][-1][0],
    }


def link_references(upstream_id, downstream_id, upstream, downstream, index):
    return {
        'departure': endpoint_reference(upstream_id, upstream, True, index),
        'arrival': endpoint_reference(downstream_id, downstream, False, index),
        'cross_sensor_identity_verified': False,
    }
