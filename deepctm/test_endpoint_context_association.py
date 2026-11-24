import copy
import unittest

import numpy as np

from .bidirectional_association import associate as baseline, motion_context
from .endpoint_context_association import BASELINE, associate, contextual_cost, corrected_cue, enrich
from .spatial_bridges import endpoint
from .validate_endpoint_context_association import qualifies

PARAMETERS = dict(vmax=30., amin=-4., amax=3.)


class EndpointContextAssociationTests(unittest.TestCase):
    def test_visible_endpoint_derivative_differs_from_window_median_without_editing_it(self):
        p = np.asarray([[t, 12*t+.5*t*t, 12+t] for t in np.arange(-3, .01, .5)])
        ep = endpoint(p, True); before = copy.deepcopy(ep)
        result = enrich(ep, p, True)
        self.assertEqual(ep, before)
        self.assertAlmostEqual(result['endpoint_time_slope']['speed_mps'], 12.)
        self.assertAlmostEqual(result['v'], 11.)
        self.assertAlmostEqual(corrected_cue(result, 1.)['v'], 12.)
        self.assertEqual(result['v'], before['v'])

    def test_speed_correction_is_bounded_and_signed_for_both_directions(self):
        for sign in (1, -1):
            e = dict(v=10.*sign, motion_context={'acceleration_mps2': sign},
                     endpoint_time_slope={'speed_mps': 15.*sign})
            self.assertEqual(corrected_cue(e, 1.)['v'], 11.*sign)
            self.assertEqual(corrected_cue(e, 2.)['v'], 12.*sign)
            self.assertEqual(e['v'], 10.*sign)

    def test_real_nonuniform_cadence_does_not_silently_disable_visible_fit(self):
        times = np.asarray([-2.82, -2.27, -1.70, -1.14, -.57, 0.])
        points = [[t, 12*t+.5*t*t, 12+t] for t in times]
        result = enrich(endpoint(points, True), points, True)
        self.assertIn('endpoint_time_slope', result)
        self.assertAlmostEqual(result['endpoint_time_slope']['speed_mps'], 12.)
        self.assertNotEqual(result['v'], corrected_cue(result, 1.)['v'])

    def test_hidden_side_context_is_rejected(self):
        p = [[t, t*10., 10.] for t in np.arange(-3, 1.1, .5)]
        with self.assertRaises(ValueError):
            enrich(dict(t=0., x=0., v=10.), p, True)

    def test_gapped_noisy_or_short_context_falls_back(self):
        p = [[t, 10*t, 10.] for t in [0, .5, 1, 3, 3.5, 4]]
        e = enrich(dict(t=4., x=40., v=10.), p, True)
        self.assertNotIn('endpoint_time_slope', e)
        self.assertIs(corrected_cue(e, 1.), e)
        malformed = enrich(dict(t=0, x=0, v=10), [[0., float('nan'), 10]], True)
        self.assertIsNone(malformed['motion_context'])

    def test_baseline_mode_is_exact_current_half_blend(self):
        rng = np.random.default_rng(83)
        for _ in range(5):
            left = [dict(t=float(i*3), x=0., v=float(rng.uniform(8, 13)), class_type='2') for i in range(8)]
            right = [dict(t=a['t']+80/a['v'], x=80., v=a['v'], class_type='2') for a in left]
            expected = baseline(left, right, PARAMETERS, **BASELINE)
            self.assertEqual(associate(left, right, PARAMETERS), expected)

    def test_missing_new_evidence_leaves_matching_and_physics_unchanged(self):
        left = [dict(t=float(i*6), x=0., v=10., class_type='2',
                     motion_context={'acceleration_mps2': 0.}) for i in range(5)]
        right = [dict(t=a['t']+8, x=80., v=10., class_type='2',
                      motion_context={'acceleration_mps2': 0.}) for a in left]
        original = copy.deepcopy((left, right))
        expected = associate(left, right, PARAMETERS)
        actual = associate(left, right, PARAMETERS, cap_mps=1.)
        self.assertEqual([(m['left'], m['right'], m['cost'], m['points']) for m in actual],
                         [(m['left'], m['right'], m['cost'], m['points']) for m in expected])
        self.assertEqual((left, right), original)

    def test_context_cannot_relax_direction_or_physical_rejection(self):
        a = dict(t=0., x=0., v=10., class_type='2', motion_context={'acceleration_mps2': 0.},
                 endpoint_time_slope={'speed_mps': 30.})
        bad = [dict(t=1., x=300., v=10., class_type='2'), dict(t=10., x=-50., v=10., class_type='2')]
        self.assertEqual(associate([a], bad, PARAMETERS, cap_mps=2.), [])

    def test_ambiguous_identical_arrivals_stay_unmatched_and_identity_is_unused(self):
        a = dict(t=0., x=0., v=10., class_type='2')
        b = dict(t=10., x=100., v=10., class_type='2')
        self.assertEqual(associate([a], [dict(b, truth_id='same'), dict(b, truth_id='other')], PARAMETERS, cap_mps=1.), [])

    def test_width_or_missing_endpoint_false_regression_blocks_promotion(self):
        base = dict(overall={'correct': 10, 'false': 1}, added_correct_unique_ids=0,
                    by_width={'20': {'false': 1}}, by_site={'s': {'false': 1}},
                    by_scenario={'missing': {'false': 1}}, by_direction={'eastbound': {'false': 1}})
        candidate = copy.deepcopy(base); candidate['overall']['correct'] = 20
        candidate['added_correct_unique_ids'] = 10
        result = {'methods': {'baseline': base, 'candidate': candidate}}
        self.assertTrue(qualifies(result, 'candidate', test=True))
        candidate['by_scenario']['missing']['false'] = 2
        self.assertFalse(qualifies(result, 'candidate', test=True))


if __name__ == '__main__':
    unittest.main()
