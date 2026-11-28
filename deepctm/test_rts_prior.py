import unittest,numpy as np
from .rts_prior import reference,dynamics,estimate
class RTSTests(unittest.TestCase):
    def test_constant_speed_and_input_immutability(self):
        before=np.array([[t,3*t] for t in np.arange(0,3,.5)]);after=np.array([[t,3*t] for t in np.arange(8,11,.5)]);old=before.copy()
        a=dict(t=2.5,x=7.5,v=3);b=dict(t=8,x=24,v=3)
        p=reference(before,after,a,b)
        np.testing.assert_allclose(p[:,1],3*p[:,0],atol=1e-6)
        np.testing.assert_allclose(before,old)
        r=estimate(before,after,a,b,dict(vmax=30,amin=-6,amax=4))
        self.assertEqual(r['state'],'candidate');self.assertAlmostEqual(r['points'][-1,1],24)
    def test_hidden_observations_rejected(self):
        before=[[t,t] for t in range(6)];after=[[t,t] for t in range(10,16)]
        with self.assertRaises(ValueError):reference(before,after,dict(t=4,x=4),dict(t=10,x=10))
    def test_covariance_positive_semidefinite(self):
        for dt in (.01,.5,10):
            _,q=dynamics(dt,.1);self.assertGreaterEqual(np.linalg.eigvalsh(q).min(),-1e-10)
