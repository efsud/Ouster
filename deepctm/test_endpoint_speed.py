import unittest
import numpy as np
from .endpoint_speed import evidence,correct,orient,reconstruct
from .spatial_bridges import endpoint

class EndpointSpeedTests(unittest.TestCase):
    def setUp(self):
        self.config=dict(negative_speed_limit_mps=.25,position_span_limit_m=.25,trend_limit_mps=.05,step_speed_limit_mps=.5)
        self.params=dict(vmax=30,amin=-6,amax=4)
    def noisy(self):return endpoint([[0,0],[.5,.01],[1,0],[1.5,-.01],[2,-.02]],True)
    def test_visible_jitter_corrected_without_mutation(self):
        a=self.noisy();ep,change=correct(a,self.config)
        self.assertLess(a['v'],0);self.assertEqual(ep['v'],0);self.assertEqual(ep['x'],a['x']);self.assertIsNotNone(change)
    def test_real_reverse_rejected(self):
        a=endpoint([[i*.5,-i*.06] for i in range(5)],True)
        self.assertIsNone(correct(a,self.config)[0])
    def test_no_evidence_no_correction(self):self.assertIsNone(correct(dict(t=0,x=0,v=-.01),self.config)[0])
    def test_westbound_evidence_oriented(self):
        a=self.noisy();b=orient(a,-1);self.assertEqual(b['velocity_evidence']['trend_speed_mps'],-a['velocity_evidence']['trend_speed_mps']);self.assertGreater(b['v'],0)
    def test_exact_positions_and_physical_motion(self):
        a=self.noisy();b=dict(t=32,x=30,v=2)
        strict=reconstruct(a,b,self.params,None);fixed=reconstruct(a,b,self.params,self.config)
        self.assertNotEqual(strict['state'],'candidate');self.assertEqual(fixed['state'],'candidate')
        np.testing.assert_allclose(fixed['points'][[0,-1],1],[a['x'],b['x']],atol=1e-6)
        self.assertGreaterEqual(fixed['points'][:,2].min(),-1e-5);self.assertEqual(len(fixed['endpoint_corrections']),1)
    def test_positive_endpoints_unchanged(self):
        a=dict(t=0,x=0,v=2);b=dict(t=30,x=60,v=2)
        strict=reconstruct(a,b,self.params,None);fixed=reconstruct(a,b,self.params,self.config)
        np.testing.assert_array_equal(strict['points'],fixed['points']);self.assertEqual(fixed['endpoint_corrections'],[])
    def test_live_prediction_is_opt_in_and_preserves_westbound(self):
        from .reconstruction_layers import prediction
        report={'selected_method':'kinematic_0.01','calibration':{'parameters':self.params}}
        a=orient(self.noisy(),-1);b=dict(t=32,x=-30,v=-2);meta={}
        self.assertIsNone(prediction(a,b,report,exact_join=True))
        points=prediction(a,b,report,exact_join=True,endpoint_policy=self.config,metadata=meta)
        self.assertIsNotNone(points);self.assertEqual(len(meta['endpoint_corrections']),1)
        self.assertEqual(meta['uncertainty'],'not_calibrated_for_endpoint_correction')
        self.assertTrue(all(y[1]<=x[1]+1e-5 for x,y in zip(points,points[1:])))
    def test_local_layer_records_correction_without_editing_observations(self):
        import copy
        from .reconstruction_layers import generate
        points=[[t,x,0.] for t,x in [(0,0),(.5,.01),(1,0),(1.5,-.01),(2,-.02),(4,.01),(4.5,.02),(5,.03),(5.5,.04),(6,.05)]]
        track={'class_type':'2','source_key':['session','car','2'],'direction':'eastbound','points':points}
        snapshot={'start':0,'end':100,'generated_at':100,'sites':[{'id':'site','station_m':0,'tracks':[track],'local_gap_candidates':[]}]}
        before=copy.deepcopy(snapshot)
        report={'state':'evaluated_ablation','selected_method':'kinematic_0.01','calibration':{'parameters':self.params},'test':{},'uncertainty':{}}
        old=generate(snapshot,report);new=generate(snapshot,report,endpoint_policy=self.config)
        self.assertEqual(len(old['within_intersection']),0);self.assertEqual(len(new['within_intersection']),1)
        self.assertEqual(new['endpoint_corrected_gaps'],1);self.assertEqual(snapshot,before)
        self.assertEqual(new['between_intersections'],old['between_intersections'])
if __name__=='__main__':unittest.main()
