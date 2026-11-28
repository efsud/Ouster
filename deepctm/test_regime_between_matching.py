import copy
import unittest
from dataclasses import asdict
from unittest.mock import patch

from .regime_between_matching import (VERSION, endpoint_group, annotate_endpoints,
                                     associate, build_additional, qualified)
from .trajectory_regime_groups import RegimeConfig, VERSION as GROUPING_VERSION
from .between_group_matching import timing_prior

PARAMS = {'vmax': 30., 'amin': -4., 'amax': 3.}


def member(group, start, end, regime='moving'):
    return dict(group_id=group, start_s=start, end_s=end, regime=regime)


def policy():
    return dict(enabled=True, version=VERSION, validation_state='complete',
                parameters=PARAMS, grouping_version=GROUPING_VERSION,
                grouping_config=asdict(RegimeConfig()), weight=.25)


class EndpointRegimeTests(unittest.TestCase):
    def test_departure_uses_final_moving_group_not_long_queue_majority(self):
        groups = [member('queue', 0, 60, 'stopped'), member('moving', 60, 65)]
        self.assertEqual(endpoint_group({'t': 65}, groups), 'moving')
        self.assertIsNone(endpoint_group({'t': 20}, groups))

    def test_no_nearest_group_across_observation_hole(self):
        self.assertIsNone(endpoint_group({'t': 20}, [member('a', 0, 19.5)]))

    def test_competing_endpoint_groups_abstain(self):
        groups = [member('a', 0, 3), member('b', 3, 6)]
        self.assertIsNone(endpoint_group({'t': 3}, groups))

    def test_same_group_boundary_is_unambiguous(self):
        self.assertEqual(endpoint_group({'t': 3}, [member('a', 0, 3), member('a', 3, 6)]), 'a')

    def test_identity_namespaced_even_for_same_group_label(self):
        site = dict(id='A', tracks=[dict(source_key=['session', '1', '2'])])
        groups = dict(assignments=[[member('same', 0, 10)]])
        a = annotate_endpoints([dict(fragment=0, t=10)], site, groups)[0]
        b = annotate_endpoints([dict(fragment=0, t=10)], dict(site, id='B'), groups)[0]
        self.assertNotEqual(a['local_identity'], b['local_identity'])

    def test_wrong_snapshot_rejected(self):
        with self.assertRaises(ValueError):
            annotate_endpoints([], dict(tracks=[{}]), dict(assignments=[]))

    def test_old_policy_cannot_enable_regime_adapter(self):
        p = policy(); self.assertTrue(qualified(p, PARAMS))
        p['version'] = 'trajectory_group_anchor_v1'
        self.assertFalse(qualified(p, PARAMS))
        self.assertEqual(build_additional({}, {'calibration': {'parameters': PARAMS}}, {}, [], p)['paths'], [])

    def test_group_labels_alone_never_supply_three_other_anchors(self):
        left = [dict(t=i*3, x=0, v=10., class_type='2', trajectory_group='L',
                     local_identity=('A', 's', str(i))) for i in range(3)]
        right = [dict(t=i*3+10, x=100, v=10., class_type='2', trajectory_group='R',
                      local_identity=('B', 's', str(i))) for i in range(3)]
        self.assertIsNone(timing_prior(left[0], right[0], left, right,
                                      [dict(left=i, right=i) for i in range(3)]))

    def test_missing_endpoint_groups_reproduces_baseline(self):
        from .bidirectional_association import associate as base
        left = [dict(t=0, x=0, v=10, class_type='2', trajectory_group=None)]
        right = [dict(t=10, x=100, v=10, class_type='2', trajectory_group=None)]
        expected = base(left, right, PARAMS, blend=.5)
        actual = associate(left, right, PARAMS)
        self.assertEqual([(m['left'], m['right']) for m in actual],
                         [(m['left'], m['right']) for m in expected])
        self.assertFalse(any(m.get('group_assistance') for m in actual))


class ReservationTests(unittest.TestCase):
    def test_previous_layers_reserved_and_original_data_untouched(self):
        snapshot = {'sites': [
            dict(id='A', name='A', station_m=0, tracks=[dict(source_key=['s', '1', '2'],
                class_type='2', direction='eastbound', points=[[0, 0, 10], [1, 10, 10], [2, 20, 10]])]),
            dict(id='B', name='B', station_m=100, tracks=[dict(source_key=['s', '2', '2'],
                class_type='2', direction='eastbound', points=[[12, 120, 10], [13, 130, 10], [14, 140, 10]])])
        ]}
        before = copy.deepcopy(snapshot)
        grouped = [dict(id='A', assignments=[[member('a', 0, 2)]]),
                   dict(id='B', assignments=[[member('b', 12, 14)]])]

        def fake_reconstruct(snap, matcher, endpoint_enricher):
            left = [dict(site='A', fragment=0, t=2, x=20, v=10, class_type='2')]
            right = [dict(site='B', fragment=0, t=12, x=120, v=10, class_type='2')]
            matches = matcher(left, right)
            return {'links': [dict(sites=['A', 'B'], direction='eastbound', paths=[
                dict(upstream_fragment=0, downstream_fragment=0, association_cost=0, ambiguity_margin=1)
                for _ in matches])]}

        proposal = [dict(left=0, right=0, cost=0, margin=1, points=[[2, 20, 10], [12, 120, 10]],
                         group_assistance=True, group_evidence={'anchor_count': 3})]
        with patch('deepctm.spatial_bridges.reconstruct', side_effect=fake_reconstruct), \
             patch('deepctm.regime_between_matching.associate', return_value=proposal), \
             patch('deepctm.reconstruction_layers.prediction', return_value=[[2, 20, 10], [12, 120, 10]]):
            for key in ('residual_color', 'trajectory_groups', 'regime_groups'):
                existing = {key: {'between_intersections': [dict(sites=['A', 'B'],
                                                               points=[[2, 20, 10], [12, 120, 10]])]}}
                result = build_additional(snapshot, {'calibration': {'parameters': PARAMS}}, existing,
                                          grouped, policy())
                self.assertEqual(result['paths'], [])
                self.assertEqual(result['diagnostics'][0]['existing_endpoint_reserved'], 1)
            result = build_additional(snapshot, {'calibration': {'parameters': PARAMS}}, {}, grouped, policy())
            self.assertEqual(len(result['paths']), 1)
            self.assertEqual(result['paths'][0]['method'], VERSION)
            self.assertFalse(result['paths'][0]['cross_sensor_identity_verified'])
        self.assertEqual(snapshot, before)


if __name__ == '__main__':
    unittest.main()
