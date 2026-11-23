import unittest
import numpy as np
from .stationary_plateau import estimate

class StationaryPlateauTests(unittest.TestCase):
    def endpoints(self):
        e={'span_m':.04,'duration_s':2.,'trend_speed_mps':.01,'max_step_speed_mps':.1,'samples':5}
        return {'t':0.,'x':100.,'v':.01,'velocity_evidence':e},{'t':20.,'x':99.98,'v':-.01,'velocity_evidence':e}
    def test_noise_estimate_is_explicit_and_does_not_edit_observations(self):
        a,b=self.endpoints();r=estimate(a,b,same_identity=True)
        self.assertEqual(r['state'],'candidate');self.assertFalse(r['exact_endpoint_interpolation'])
        self.assertEqual(a['x'],100.);self.assertEqual(b['x'],99.98)
        np.testing.assert_allclose(r['points'][:,1],99.99);np.testing.assert_allclose(r['points'][:,2],0.)
        self.assertLessEqual(max(abs(v) for v in r['endpoint_position_residual_m']),.05)
    def test_unknown_identity_moving_context_and_long_gap_reject(self):
        a,b=self.endpoints();self.assertEqual(estimate(a,b)['state'],'unavailable')
        b['v']=1.;self.assertEqual(estimate(a,b,True)['state'],'unavailable')
        a,b=self.endpoints();b['t']=60.;self.assertEqual(estimate(a,b,True)['state'],'unavailable')
        a,b=self.endpoints();b['x']=101.;self.assertEqual(estimate(a,b,True)['state'],'unavailable')
