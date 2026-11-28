import copy
import unittest
from dataclasses import asdict

import numpy as np

from .local_group_prior import prepare as peer_prepare
from .regime_group_learning import (FEATURES, VERSION, apply, features, fingerprint,
                                    fit, predict, prepare, propose, training_label, weight)
from .test_local_group_prior import FakeGroups, GroupPriorTests
from .validate_regime_group_learning import masks, summary


class RegimeGroupsStub:
    def __init__(self, indices):
        self.indices, self.calls = indices, []

    def select_donors(self, target, a, b, excluded_identity):
        self.calls.append((copy.deepcopy(target), a, b, excluded_identity))
        return dict(group_id='local-regime', donor_indices=self.indices)


class RegimeLearningTests(unittest.TestCase):
    def prepared(self, sign=1):
        site, target, a, b = GroupPriorTests().fixture(sign)
        return peer_prepare(site, target, a, b, FakeGroups(range(5)))

    def model(self):
        values = features(self.prepared())
        rows = [dict(identity_hash=str(i), features=(values+i*.01).tolist(),
                     target_weight=.5) for i in range(25)]
        return fit(rows)

    def test_true_supervised_fit_and_model_schema_validation(self):
        model = self.model()
        self.assertEqual(model['state'], 'trained')
        self.assertEqual(model['independent_ids'], 25)
        self.assertAlmostEqual(weight(model, features(self.prepared())), .5)
        broken = copy.deepcopy(model); broken['coefficients'][0] = .2
        with self.assertRaises(ValueError):
            weight(broken, features(self.prepared()))
        broken['fingerprint'] = fingerprint(broken)
        broken['scale'][0] = 0; broken['fingerprint'] = fingerprint(broken)
        with self.assertRaises(ValueError):
            weight(broken, features(self.prepared()))

    def test_insufficient_independent_training_not_replaced_by_repeated_masks(self):
        rows = [dict(identity_hash='one', features=[1.]*len(FEATURES), target_weight=.7)]*100
        result = fit(rows)
        self.assertEqual(result['state'], 'insufficient_training')
        self.assertEqual(result['independent_ids'], 1)

    def test_supervision_changes_predictions_by_visible_features(self):
        rows = []
        for i in range(30):
            x = [1.]*len(FEATURES); x[0] = i/29
            rows.append(dict(identity_hash=str(i), features=x, target_weight=i/29))
        model = fit(rows, ridge=1.)
        low = [1.]*len(FEATURES); low[0] = 0
        high = [1.]*len(FEATURES); high[0] = 1
        self.assertLess(weight(model, low), .1)
        self.assertGreater(weight(model, high), .9)

    def test_nan_training_features_or_labels_are_rejected(self):
        rows = [dict(identity_hash=str(i), features=[1.]*len(FEATURES), target_weight=.5) for i in range(25)]
        rows[0]['features'][0] = float('nan')
        with self.assertRaises(ValueError):
            fit(rows)

    def test_hidden_target_rejected_and_same_id_different_class_excluded(self):
        site, target, a, b = GroupPriorTests().fixture()
        original = copy.deepcopy((site, target))
        groups = RegimeGroupsStub(range(5))
        result = prepare(site, target, a, b, groups)
        self.assertEqual(result['state'], 'prepared')
        self.assertEqual(result['donor_count'], 3)
        self.assertNotIn(['session', 'target'], result['donor_identities'])
        self.assertEqual(groups.calls[0][-1], ('session', 'target'))
        self.assertEqual((site, target), original)
        target['points'].append([15., 150., 10.])
        with self.assertRaises(ValueError):
            prepare(site, target, a, b, groups)
        self.assertEqual(len(groups.calls), 1)

    def test_predictions_exact_endpoints_finite_both_directions_no_mutation(self):
        model = self.model()
        for sign in (1, -1):
            prepared = self.prepared(sign)
            saved = prepared['reference'].copy()
            result = predict(prepared, dict(vmax=25., amin=-6., amax=4.), model)
            self.assertEqual(result['state'], 'candidate')
            self.assertTrue(np.all(np.isfinite(result['points'])))
            np.testing.assert_allclose(result['points'][[0, -1], 1:],
                [[100*sign, 10], [200*sign, 10]], atol=1e-7)
            np.testing.assert_array_equal(prepared['reference'], saved)

    def test_training_hidden_labels_cannot_enter_predict(self):
        p = self.prepared(); model = self.model()
        prior = predict(p, dict(vmax=25., amin=-6., amax=4.), model)
        truth = p['reference'].copy()
        # Training-only labels can change with truth; prediction API has no truth
        # argument and never reads these labels from the prepared evidence.
        self.assertTrue(0 <= training_label(p, truth) <= 1)
        p['target_weight'] = 1.; p['hidden_truth'] = truth*1000
        result = predict(p, dict(vmax=25., amin=-6., amax=4.), model)
        np.testing.assert_array_equal(prior['points'], result['points'])

    def test_unqualified_policy_cannot_replace_baseline(self):
        site, target, a, b = GroupPriorTests().fixture()
        result = propose(site, target, a, b, {}, {'enabled': False})
        self.assertEqual(result['reason'], 'policy_not_qualified')

    def adapter_fixture(self):
        from .trajectory_regime_groups import RegimeGroupConfig
        site, layers, params, old_policy = GroupPriorTests().wrapper_fixture()
        policy = dict(old_policy, version=VERSION, group_configuration=asdict(RegimeGroupConfig()),
                      model=self.model(), evidence='frozen-test-report.json', snapshot_sha256='test-fingerprint')
        return site, layers, params, policy

    def test_adapter_preserves_observations_and_between_site_paths(self):
        site, layers, params, policy = self.adapter_fixture()
        original = copy.deepcopy((site, layers))
        result = apply({'sites': [site]}, layers, policy, params, {'site': RegimeGroupsStub(range(5))})
        self.assertEqual(result['regime_learning_review']['replaced'], 1)
        self.assertEqual(result['between'], layers['between'])
        self.assertEqual(result['within_intersection'][0]['baseline_provenance']['method'], 'baseline')
        self.assertEqual((site, layers), original)

    def test_adapter_disabled_changed_or_corrupted_policy_retains_baseline(self):
        site, layers, params, policy = self.adapter_fixture()
        for patch in ({'enabled': False}, {'parameters': {}}, {'group_configuration': {}}, {'model': {}},
                      {'validation_state': 'running'}, {'snapshot_sha256': None}):
            result = apply({'sites': [site]}, layers, policy | patch, params)
            self.assertEqual(result['within_intersection'], layers['within_intersection'])
            self.assertEqual(result['regime_learning_review']['state'], 'disabled')

    def test_adapter_requires_class2_same_identity_gap_and_respects_runtime(self):
        site, layers, params, policy = self.adapter_fixture()
        for patch in ({'class_type': '3'}, {'identity': 'different_sensor_candidate'},
                      {'identity_key': ['unknown', 'target']}):
            changed = copy.deepcopy(layers); changed['within_intersection'][0].update(patch)
            result = apply({'sites': [site]}, changed, policy, params)
            self.assertEqual(result['within_intersection'], changed['within_intersection'])
            self.assertEqual(result['regime_learning_review']['attempted'], 0)
        result = apply({'sites': [site]}, layers, policy, params, max_seconds=0)
        self.assertEqual(result['within_intersection'], layers['within_intersection'])
        self.assertTrue(result['regime_learning_review']['budget_exhausted'])
        site['tracks'][0]['points'].append([15., 150., 10.])
        result = apply({'sites': [site]}, layers, policy, params)
        self.assertEqual(result['within_intersection'], layers['within_intersection'])
        self.assertEqual(result['regime_learning_review']['attempted'], 0)

    def test_mask_generation_never_spans_existing_outage(self):
        tr = dict(direction='eastbound', points=[[t, 10*t, 10.] for t in np.arange(0, 60.1, .5)])
        tr['points'] = [p for p in tr['points'] if p[0] < 27 or p[0] > 33]
        for regime, (a, b, truth) in masks(tr, 10):
            self.assertFalse(a['t'] < 27 and b['t'] > 33)
            self.assertTrue(np.all((truth[:, 0] > a['t']) & (truth[:, 0] < b['t'])))

    def test_fallback_summary_uses_all_baseline_masks(self):
        metric = dict(mae_m=1., rmse_m=1., speed_mae_mps=1., max_error_m=1.,
                      stop_time_error_s=0., actual_stop=False, predicted_stop=False,
                      moving=True, physics_violation=False)
        rows = [dict(site='s', identity_hash=str(i), gap_s=5, regime='moving',
                     metrics={'kinematic': metric, **({'new': metric | {'mae_m': 0.}} if i == 0 else {})})
                for i in range(3)]
        result = summary(rows, 'new')
        self.assertEqual(result['common']['n'], 1)
        self.assertEqual(result['fallback_included']['n'], 3)
        self.assertAlmostEqual(result['fallback_included']['candidate']['mae_m'], 2/3)


if __name__ == '__main__':
    unittest.main()
