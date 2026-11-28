import copy
import unittest

import numpy as np

from .instantaneous_boundary_retry import boundary_fit, reconstruct, DEFAULTS
from .spatial_bridges import endpoint


class InstantaneousBoundaryTests(unittest.TestCase):
    report=dict(selected_method='kinematic_0.01',calibration=dict(parameters=dict(vmax=24.5174,amin=-6.,amax=4.)))

    def accelerating_fixture(self, sign=1):
        left=[[float(t),0.,0.] for t in np.arange(-4,.01,.5)]
        right=[[float(t),sign*(t-3)**2,2*(t-3)] for t in np.arange(3,7.01,.5)]
        return left,right,endpoint(left,True),endpoint(right,False)

    def test_recovers_boundary_instantaneous_speed_from_visible_acceleration(self):
        for sign in (1,-1):
            left,right,a,b=self.accelerating_fixture(sign)
            original=copy.deepcopy((left,right,a,b))
            self.assertAlmostEqual(abs(b['v']),2.)
            result=reconstruct('site',left,right,a,b,'eastbound' if sign==1 else 'westbound',self.report)
            self.assertEqual(result['state'],'candidate')
            np.testing.assert_allclose(result['points'][:,1:],0.,atol=1e-6)
            self.assertEqual((left,right,a,b),original)
            self.assertAlmostEqual(result['boundary_fits'][1]['acceleration_mps2'],2.,places=5)

    def test_does_not_force_inconsistent_near_stationary_gap_into_fast_observation(self):
        left,right,a,b=self.accelerating_fixture()
        right=[[float(t),.02+4*(t-3),4.] for t in np.arange(3,7.01,.5)]
        b=endpoint(right,False)
        result=reconstruct('site',left,right,a,b,'eastbound',self.report)
        self.assertEqual(result['state'],'unavailable')
        self.assertEqual(result['reason'],'no_visible_acceleration_bias')

    def test_existing_baseline_is_numerically_unchanged(self):
        left,right,a,b=self.accelerating_fixture()
        existing=np.array([[0.,0.,0.],[3.,0.,0.]])
        result=reconstruct('site',left,right,a,b,'eastbound',self.report,established=existing)
        self.assertEqual(result['state'],'baseline_retained')
        np.testing.assert_array_equal(result['points'],existing)

    def test_wrong_side_or_hidden_points_are_rejected_before_fitting(self):
        left,right,a,b=self.accelerating_fixture()
        for altered in (left+[[1.,0.,0.]],left+[[8.,0.,0.]],left[:-1]):
            with self.assertRaises(ValueError):
                reconstruct('site',altered,right,a,b,'eastbound',self.report)

    def test_bad_fit_reverse_context_and_adjustment_gate_abstain(self):
        left,right,a,b=self.accelerating_fixture()
        result=reconstruct('site',left,right,a,b,'eastbound',self.report,
                           DEFAULTS|{'max_speed_adjustment_mps':.5})
        self.assertEqual(result['reason'],'speed_adjustment_exceeds_evidence_gate')
        bad=copy.deepcopy(right);bad[2][1]+=10
        result=boundary_fit(bad,False,1,self.report['calibration']['parameters'])
        self.assertEqual(result['state'],'unavailable')
        reverse=copy.deepcopy(a);reverse['v']=-1
        result=reconstruct('site',left,right,reverse,b,'eastbound',self.report,established=None)
        self.assertEqual(result['reason'],'reverse_endpoint_evidence')

    def test_gap_and_existing_site_exclusion_scope(self):
        left,right,a,b=self.accelerating_fixture()
        result=reconstruct('site',left,right,a,b,'eastbound',self.report,classes=('3','3'))
        self.assertEqual(result['reason'],'outside_validated_class_scope')
        negative=copy.deepcopy(a);negative['v']=-.05
        result=reconstruct('OBC-AG-SA-C257223',left,right,negative,b,'eastbound',self.report,established=None)
        self.assertEqual(result['reason'],'existing_stationary_noise_site_exclusion')

    def test_context_gap_and_nonfinite_input_rejected(self):
        left,right,a,b=self.accelerating_fixture()
        malformed=copy.deepcopy(right);malformed[1][1]=float('nan')
        self.assertEqual(boundary_fit(malformed,False,1,self.report['calibration']['parameters'])['state'],'unavailable')
        sparse=[[i*2.,i*2.,1.] for i in range(5)]
        self.assertEqual(boundary_fit(sparse,False,1,self.report['calibration']['parameters'])['state'],'unavailable')


if __name__=='__main__':unittest.main()
