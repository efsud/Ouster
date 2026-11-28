"""Scientific invariants for observed local motion grouping; synthetic checks."""
import copy
import unittest

from .trajectory_regime_groups import (
    RegimeConfig, RegimeGroupConfig, TrajectoryRegimeGroups, group, segments,
)


def track(obj, lag=0., speed=10., slope=None, lateral=0., direction='eastbound',
          movement='WE', role='through', points=None):
    sign = 1 if direction == 'eastbound' else -1
    slope = speed if slope is None else slope
    return dict(source_key=['session', str(obj), '2'], class_type='2', direction=direction,
                points=points if points is not None else [[lag+i*.5, sign*i*.5*slope, speed] for i in range(41)],
                lateral_start_m=lateral, lateral_end_m=lateral,
                movement=dict(movement=movement, role=role))


def site(*tracks):
    return dict(id='synthetic-site', tracks=list(tracks))


def stopped_then_moving(obj, lag=0., station_offset=0.):
    points = [[lag+i*.5, station_offset + max(0., i*.5-12.)*10.,
               0. if i*.5 <= 12. else 10.] for i in range(65)]
    return track(obj, points=points)


class TrajectoryRegimeGroupTests(unittest.TestCase):
    def test_same_vehicle_has_distinct_stopped_and_moving_memberships(self):
        s = site(*(stopped_then_moving(str(i), i*2., -i*4.) for i in range(4)))
        before = copy.deepcopy(s)
        result = group(s)
        self.assertEqual(s, before)
        self.assertIs(RegimeConfig, RegimeGroupConfig)
        self.assertEqual({g['regime'] for g in result['groups']}, {'stopped', 'moving'})
        for memberships in result['assignments']:
            self.assertEqual({m['regime'] for m in memberships}, {'stopped', 'moving'})
            self.assertGreaterEqual(len({m['group_id'] for m in memberships}), 2)
            for m in memberships:
                p = s['tracks'][m['track_index']]['points']
                self.assertEqual(m['start_s'], p[m['start_index']][0])
                self.assertEqual(m['end_s'], p[m['end_index']][0])
        self.assertTrue(all(g['identity_count'] == 4 for g in result['groups']))
        self.assertTrue(all(g['observed_only'] and not g['envelope_is_estimated_trajectory'] for g in result['groups']))

    def test_numeric_speed_slope_direction_location_and_time_are_separate_checks(self):
        anchors = [track('a'), track('b', lag=2)]
        bad = [track('c', lag=100), track('c', lateral=9), track('c', speed=18),
               track('c', speed=10, slope=17), track('c', direction='westbound', movement='EW'),
               track('c', movement='WN'), track('c', role='corridor_exit')]
        for other in bad:
            with self.subTest(other=other):
                self.assertEqual(group(site(*anchors, other))['groups'], [])

    def test_saturated_green_colors_do_not_make_22_and_35_mps_equal(self):
        result = group(site(track('a', speed=22), track('b', speed=23), track('c', speed=35)))
        self.assertEqual(result['groups'], [])

    def test_one_initial_zero_speed_sample_is_not_a_stopped_segment(self):
        t = track('a')
        t['points'][0][2] = 0.
        ds = segments(t)
        self.assertTrue(ds)
        self.assertNotIn('stopped', {d['regime'] for d in ds})

    def test_same_id_fragments_or_class_changes_cannot_supply_three_peers(self):
        a = track('same'); b = track('same', lag=1)
        b['class_type'] = '4'; b['source_key'][2] = '4'
        self.assertEqual(group(site(a, b, track('other', lag=2)))['groups'], [])

    def test_original_gaps_never_become_observed_support(self):
        p = [[i*.5, i*5., 10.] for i in range(9)] + [[15+i*.5, 150+i*5., 10.] for i in range(9)]
        s = site(*(track(str(i), points=copy.deepcopy(p)) for i in range(3)))
        result = group(s)
        self.assertTrue(result['groups'])
        for memberships in result['assignments']:
            self.assertEqual(len(memberships), 2)
            for m in memberships:
                self.assertFalse(m['start_index'] < 9 <= m['end_index'])
        for g in result['groups']:
            self.assertFalse(any(4.5 < row[0] < 15 for row in g['envelope']))
            for row in g['envelope']:
                observed = [p for tr in s['tracks'] for p in tr['points'] if int(p[0]) == int(row[0])]
                self.assertTrue(observed)
                self.assertEqual(row[1], min(p[1] for p in observed))
                self.assertEqual(row[2], max(p[1] for p in observed))

    def test_invalid_identity_clock_missing_lateral_and_estimates_abstain(self):
        alterations = [{'source_key': []}, {'source': 'inferred'}, {'method': 'predicted'},
                       {'lateral_start_m': None, 'lateral_end_m': None}]
        for alteration in alterations:
            self.assertEqual(group(site(track('a'), track('b'), dict(track('c'), **alteration)))['groups'], [])
        broken = track('c'); broken['points'][5][0] = 0
        self.assertEqual(group(site(track('a'), track('b'), broken))['groups'], [])

    def test_stopped_groups_do_not_require_a_shared_station_crossing(self):
        tracks = [track(str(i), speed=0, points=[[j*.5+i, i*5., 0.] for j in range(41)]) for i in range(4)]
        result = group(site(*tracks))
        self.assertEqual(len(result['groups']), 1)
        self.assertEqual(result['groups'][0]['regime'], 'stopped')
        self.assertEqual(result['groups'][0]['aggregate']['slope_median_mps'], 0.)

    def test_unknown_movement_and_role_do_not_bridge_conflicting_known_labels(self):
        for field, other in [('movement', 'WN'), ('role', 'corridor_exit')]:
            tracks = [track('u', movement=None, role=None), track('a'), track('b'), track('c'), track('d')]
            tracks[3]['movement'][field] = tracks[4]['movement'][field] = other
            result = group(site(*tracks))
            for g in result['groups']:
                self.assertLessEqual(len(g['movement_codes']), 1)
                self.assertLessEqual(len(g['movement_roles']), 1)

    def test_density_group_does_not_chain_across_a_whole_recording(self):
        result = group(site(*(track(str(i), lag=15*i) for i in range(15))))
        self.assertGreater(len(result['groups']), 1)
        self.assertTrue(all(g['end_s']-g['start_s'] <= 60 for g in result['groups']))

    def test_all_target_id_fragments_are_excluded_and_hidden_values_are_irrelevant(self):
        target = track('target', lag=2)
        duplicate = track('target', lag=3); duplicate['class_type'] = '4'; duplicate['source_key'][2] = '4'
        s = site(target, duplicate, *(track('peer'+str(i), lag=i*2) for i in range(4)))
        visible = copy.deepcopy(target)
        visible['points'] = [p for p in visible['points'] if not 7 < p[0] < 12]
        modified = copy.deepcopy(s)
        for tr in modified['tracks'][:2]:
            for p in tr['points']:
                if 7 < p[0] < 12:
                    p[1] += 900.; p[2] = 100.
        a, b = {'t': 7.}, {'t': 12.}
        ma, mb = TrajectoryRegimeGroups(s), TrajectoryRegimeGroups(modified)
        ra, rb = ma.select_donors(visible, a, b), mb.select_donors(visible, a, b)
        self.assertIsNotNone(ra)
        self.assertEqual(ra, rb)
        self.assertTrue(all(i >= 2 for i in ra['donor_indices']))
        self.assertEqual(ma.group(('session', 'target')), mb.group(('session', 'target')))
        self.assertEqual(ma.group(('session', 'target'))['assignments'][:2], [[], []])

    def test_hidden_target_points_passed_to_selector_are_rejected(self):
        target = track('target')
        m = TrajectoryRegimeGroups(site(target, track('a'), track('b'), track('c')))
        with self.assertRaises(ValueError):
            m.select_donors(target, {'t': 5.}, {'t': 10.})

    def test_only_two_other_ids_cannot_classify_a_target(self):
        target = track('target')
        m = TrajectoryRegimeGroups(site(target, track('a'), track('b')))
        self.assertIsNone(m.classify_visible(target))

    def test_westbound_slope_stays_signed_while_forward_slope_is_positive(self):
        result = group(site(*(track(str(i), lag=i*2, direction='westbound', movement='EW') for i in range(3))))
        self.assertEqual(len(result['groups']), 1)
        g = result['groups'][0]
        self.assertAlmostEqual(g['aggregate']['slope_median_mps'], -10.)
        self.assertTrue(all(m['forward_slope_mps'] == 10. for m in g['members']))


if __name__ == '__main__':
    unittest.main()
