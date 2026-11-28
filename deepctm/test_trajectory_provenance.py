import copy
import unittest
from unittest.mock import patch
from .trajectory_provenance import fragment_index, endpoint_reference


class ProvenanceTests(unittest.TestCase):
    def track(self, code='2', start=0):
        return dict(source_key=['session', 'object', code], class_type=code,
                    direction='eastbound', points=[[start+i/2, 10*(start+i/2), 10] for i in range(5)])

    def test_filtered_copy_keeps_original_index(self):
        vehicle = self.track()
        snapshot = {'sites': [dict(id='a', tracks=[self.track('1'), vehicle])]}
        index = fragment_index(snapshot)
        copied = dict(vehicle, internal_chain_endpoints=[])
        ref = endpoint_reference('a', copied, True, index)
        self.assertEqual(ref['source_fragment_indices'], [1])
        self.assertEqual(ref['observed_endpoint'], vehicle['points'][-1])

    def test_same_object_number_different_site_or_fragment_is_distinct(self):
        a = self.track()
        b = self.track(start=30)
        index = fragment_index({'sites': [dict(id='a', tracks=[a, b]), dict(id='b', tracks=[a])]})
        refs = [endpoint_reference(site, tr, True, index) for site, tr in [('a', a), ('a', b), ('b', a)]]
        self.assertEqual(len({r['fragment_id'] for r in refs}), 3)
        self.assertTrue(all(r['identity_scope'] == 'sensor_session_object_only' for r in refs))

    def test_duplicate_source_fragments_are_explicit(self):
        tr = self.track()
        index = fragment_index({'sites': [dict(id='a', tracks=[tr, copy.deepcopy(tr)])]})
        self.assertEqual(endpoint_reference('a', tr, False, index)['source_fragment_indices'], [0, 1])

    def test_baseline_link_publishes_provenance_after_class_filtering(self):
        from .reconstruction_layers import generate
        a, b = self.track(), self.track(start=10)
        snapshot = dict(start=0, end=100, generated_at=1, sites=[
            dict(id='a', tracks=[self.track('10'), a], local_gap_candidates=[]),
            dict(id='b', tracks=[self.track('10', 10), b], local_gap_candidates=[])])
        path = dict(upstream_fragment=0, downstream_fragment=0,
                    association_cost=0, ambiguity_margin=1)
        link = dict(sites=['a', 'b'], direction='eastbound', paths=[path])
        report = dict(state='evaluated_ablation', selected_method='M1_linear',
                      calibration={'parameters': {'vmax': 35, 'amin': -4, 'amax': 3}}, test={}, uncertainty={})
        with patch('deepctm.reconstruction_layers.reconstruct', return_value={'links': [link]}):
            result = generate(snapshot, report)
        refs = result['between_intersections'][0]['endpoint_provenance']
        self.assertEqual(refs['departure']['source_fragment_indices'], [1])
        self.assertEqual(refs['arrival']['source_fragment_indices'], [1])
        self.assertFalse(refs['cross_sensor_identity_verified'])
