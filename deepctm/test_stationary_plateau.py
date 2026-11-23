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

    def test_renderer_option_preserves_observations_and_labels_residual(self):
        import copy
        from .reconstruction_layers import prediction
        from .endpoint_speed import orient
        report={'selected_method':'kinematic_0.01','calibration':{'parameters':dict(vmax=30,amin=-6,amax=4)}}
        for sign in (1,-1):
            a,b=self.endpoints();a=orient(a,sign);b=orient(b,sign);before=copy.deepcopy((a,b));meta={}
            self.assertIsNone(prediction(a,b,report,exact_join=True))
            result=prediction(a,b,report,exact_join=True,stationary_plateau=True,metadata=meta)
            self.assertIsNotNone(result);self.assertEqual((a,b),before)
            self.assertFalse(meta['exact_endpoint_interpolation'])
            self.assertEqual(meta['estimation_model'],'bounded_stationary_latent_position')
            self.assertAlmostEqual(a['x']-result[0][1],meta['endpoint_position_residual_m'][0])
            self.assertAlmostEqual(b['x']-result[-1][1],meta['endpoint_position_residual_m'][1])
            self.assertEqual(meta['observed_endpoint_speeds_mps'],[a['v'],b['v']])

    def test_layer_never_applies_plateau_at_excluded_site(self):
        from .reconstruction_layers import generate
        a,b=self.endpoints()
        snapshot={'start':0,'end':100,'generated_at':100,'sites':[{'id':'S','station_m':0,'tracks':[],
            'local_gap_candidates':[{'class_type':'2','source_key':['session','car','2'],'a':a,'b':b}]}]}
        report={'state':'evaluated_ablation','selected_method':'kinematic_0.01','calibration':{'parameters':dict(vmax=30,amin=-6,amax=4)},'test':{},'uncertainty':{}}
        enabled=generate(snapshot,report,stationary_plateau=True)
        excluded=generate(snapshot,report,stationary_plateau=True,endpoint_excluded_sites=['S'])
        self.assertEqual(len(enabled['within_intersection']),1)
        self.assertEqual(excluded['within_intersection'],[])
        self.assertEqual(enabled['between_intersections'],[])
