import unittest
from .reconstruction_layers import finch_endpoint_config

class FinchEndpointConfigTests(unittest.TestCase):
    def test_only_reviewed_sites_are_enabled(self):
        model={'endpoint_policy':{'negative_speed_limit_mps':.1},'excluded_sites':['A','B','C']}
        override={'version':'stationary_noise_correction_v1','parameters':model['endpoint_policy'],'enabled_sites':['B']}
        self.assertEqual(finch_endpoint_config(model,override)['excluded_sites'],['A','C'])
        self.assertEqual(model['excluded_sites'],['A','B','C'])
        self.assertEqual(finch_endpoint_config(model)['excluded_sites'],['A','B','C'])
    def test_unvalidated_parameter_change_rejected(self):
        with self.assertRaises(ValueError):
            finch_endpoint_config({'endpoint_policy':{'limit':.1}}, {'version':'stationary_noise_correction_v1','parameters':{'limit':1},'enabled_sites':['B']})
