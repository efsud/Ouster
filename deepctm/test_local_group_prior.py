import copy
import unittest
from dataclasses import asdict

import numpy as np

from .local_group_prior import DEFAULTS, apply, prepare, predict
from .trajectory_groups import GroupConfig


class FakeGroups:
    def __init__(self, indices):
        self.indices = indices
        self.calls = []

    def classify_visible(self, target, excluded_identity):
        self.calls.append((copy.deepcopy(target), excluded_identity))
        return {'group_id': 'test-group', 'donor_indices': self.indices}


class GroupPriorTests(unittest.TestCase):
    def fixture(self, sign=1):
        def track(ident, offset=0):
            return {'source_key': ['session', ident, '2'], 'class_type': '2',
                    'direction': 'eastbound' if sign == 1 else 'westbound',
                    'points': [[float(t), sign*(10*t+offset), 10.] for t in np.arange(0, 30.1, .5)]}
        original = track('target')
        target = dict(original, points=[p for p in original['points'] if p[0] <= 10 or p[0] >= 20])
        donors = [original, dict(original, source_key=['session', 'target', '3'])]
        donors += [track(str(i), offset) for i, offset in enumerate((-5, 0, 5))]
        return {'id': 'site', 'tracks': donors}, target, dict(t=10., x=100.*sign, v=10.*sign), dict(t=20., x=200.*sign, v=10.*sign)

    def test_excludes_same_identity_all_classes_and_does_not_mutate_observed(self):
        site, target, a, b = self.fixture()
        before = copy.deepcopy((site, target)); groups = FakeGroups(list(range(5)))
        prepared = prepare(site, target, a, b, groups)
        self.assertEqual(prepared['state'], 'prepared')
        self.assertEqual(prepared['donor_count'], 3)
        self.assertNotIn(['session', 'target'], prepared['donor_identities'])
        self.assertEqual(groups.calls[0][1], ('session', 'target'))
        self.assertTrue(all(p[0] <= 10 or p[0] >= 20 for p in groups.calls[0][0]['points']))
        result = predict(prepared, {'vmax': 25., 'amin': -6., 'amax': 4.})
        self.assertEqual(result['state'], 'candidate')
        np.testing.assert_allclose(result['points'][[0, -1], 1:], [[100, 10], [200, 10]], atol=1e-7)
        self.assertEqual((site, target), before)

    def test_westbound_preserves_signed_position_and_positive_speed(self):
        site, target, a, b = self.fixture(-1)
        result = predict(prepare(site, target, a, b, FakeGroups(range(5))), {'vmax': 25., 'amin': -6., 'amax': 4.})
        self.assertEqual(result['state'], 'candidate')
        np.testing.assert_allclose(result['points'][[0, -1], 1:], [[-100, 10], [-200, 10]], atol=1e-7)

    def test_hidden_target_is_rejected_before_grouping(self):
        site, target, a, b = self.fixture()
        target['points'].insert(21, [12., 120., 10.])
        groups = FakeGroups(range(5))
        with self.assertRaises(ValueError):
            prepare(site, target, a, b, groups)
        self.assertEqual(groups.calls, [])

    def test_donor_missing_gap_is_not_interpolated(self):
        site, target, a, b = self.fixture()
        for donor in site['tracks'][2:]:
            donor['points'] = [p for p in donor['points'] if p[0] < 11 or p[0] > 19]
        result = prepare(site, target, a, b, FakeGroups(range(5)))
        self.assertEqual(result['state'], 'unavailable')

    def test_repeated_fragment_is_one_donor_and_requires_three_identities(self):
        site, target, a, b = self.fixture()
        site['tracks'][4]['source_key'] = site['tracks'][3]['source_key']
        result = prepare(site, target, a, b, FakeGroups(range(5)))
        self.assertEqual(result['reason'], 'insufficient_continuous_group_donors')
        self.assertEqual(result['donor_count'], 2)

    def test_physics_infeasibility_never_publishes(self):
        site, target, a, b = self.fixture()
        prepared = prepare(site, target, a, b, FakeGroups(range(5)))
        prepared['b']['x'] = 500.
        result = predict(prepared, {'vmax': 25., 'amin': -6., 'amax': 4.})
        self.assertEqual(result['state'], 'infeasible')

    def wrapper_fixture(self):
        site, target, a, b = self.fixture()
        for tr in site['tracks'][:2]:
            tr['points'] = target['points']
        layers = {'within_intersection': [{'site': 'site', 'identity_key': ['session', 'target'],
                            'identity': 'same_sensor_session_id', 'direction': 'eastbound',
                            'class_type': '2', 'method': 'baseline',
                            'points': [[10., 100., 10.], [20., 200., 10.]]}],
                  'between': [{'untouched': True}]}
        params = {'vmax': 25., 'amin': -6., 'amax': 4.}
        policy = dict(version='trajectory_group_peer_shape_v1', enabled=True,
                      configuration=DEFAULTS, group_configuration=asdict(GroupConfig()),
                      validation_state='complete', parameters=params,
                      enabled_sites=['site'], weight=.5)
        return site, layers, params, policy

    def test_wrapper_only_replaces_exact_existing_local_gap(self):
        site, layers, params, policy = self.wrapper_fixture()
        original = copy.deepcopy((site, layers))
        result = apply({'sites': [site]}, layers, policy, params, {'site': FakeGroups(range(5))})
        self.assertEqual(result['group_prior_review']['replaced'], 1)
        self.assertEqual(result['between'], layers['between'])
        self.assertEqual(result['within_intersection'][0]['baseline_provenance']['method'], 'baseline')
        self.assertEqual((site, layers), original)

    def test_wrapper_disabled_or_changed_policy_retains_baseline(self):
        site, layers, params, policy = self.wrapper_fixture()
        for patch in ({'enabled': False}, {'parameters': {}}, {'group_configuration': {}}, {'validation_state': 'running'}):
            result = apply({'sites': [site]}, layers, policy | patch, params)
            self.assertEqual(result['within_intersection'], layers['within_intersection'])
            self.assertEqual(result['group_prior_review']['state'], 'disabled')

    def test_wrapper_refuses_to_replace_observed_data(self):
        site, layers, params, policy = self.wrapper_fixture()
        site['tracks'][0]['points'] = sorted(site['tracks'][0]['points'] + [[15., 150., 10.]])
        result = apply({'sites': [site]}, layers, policy, params)
        self.assertEqual(result['within_intersection'], layers['within_intersection'])
        self.assertEqual(result['group_prior_review']['attempted'], 0)


if __name__ == '__main__':
    unittest.main()
