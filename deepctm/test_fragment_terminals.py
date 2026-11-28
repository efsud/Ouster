import copy
import unittest
from .fragment_terminals import mark


def fixture():
    tracks = [dict(source_key=['session', 'car', '2'], points=[[0, 0, 5], [2, 10, 5]]),
              dict(source_key=['session', 'car', '2'], points=[[4, 20, 5], [6, 30, 5]])]
    snapshot = dict(sites=[dict(id='site', tracks=tracks)])
    path = dict(site='site', identity_key=['session', 'car'],
                identity='same_sensor_session_id', points=[[2, 10, 5], [4, 20, 5]])
    return snapshot, path


class TerminalTests(unittest.TestCase):
    def test_only_internal_ends_blocked_and_observations_unchanged(self):
        snapshot, path = fixture(); original = copy.deepcopy(snapshot)
        out = mark(snapshot, [path])['sites'][0]['tracks']
        self.assertEqual(out[0]['internal_chain_endpoints'], ['departure'])
        self.assertEqual(out[1]['internal_chain_endpoints'], ['arrival'])
        self.assertEqual(snapshot, original)
        self.assertEqual([t['points'] for t in out], [t['points'] for t in original['sites'][0]['tracks']])

    def test_no_cross_identity_or_cross_site_or_unverified_link(self):
        for field, value in [('site', 'other'), ('identity_key', ['other-session', 'car']),
                             ('identity', 'unverified_same_site_changed_id')]:
            snapshot, path = fixture(); path[field] = value
            self.assertFalse(any(t['internal_chain_endpoints'] for t in mark(snapshot, [path])['sites'][0]['tracks']))

    def test_duplicate_or_noncoincident_endpoint_does_not_block(self):
        snapshot, path = fixture()
        snapshot['sites'][0]['tracks'].append(copy.deepcopy(snapshot['sites'][0]['tracks'][0]))
        self.assertFalse(any(t['internal_chain_endpoints'] for t in mark(snapshot, [path])['sites'][0]['tracks']))
        snapshot, path = fixture(); path['points'][0][1] += 1
        self.assertFalse(any(t['internal_chain_endpoints'] for t in mark(snapshot, [path])['sites'][0]['tracks']))
