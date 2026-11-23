import unittest
import numpy as np
from .long_bridge import prediction
from .trajectory_reconstruction import grid
class LongBridgeTests(unittest.TestCase):
    params={'vmax':30.,'amin':-4.,'amax':3.}
    def test_default_grid_does_not_silently_extend(self):
        with self.assertRaises(ValueError):grid({'t':0},{'t':180})
    def test_explicit_long_link_preserves_constant_motion(self):
        for sign in (1,-1):
            p=prediction({'t':0,'x':0,'v':10*sign},{'t':180,'x':1800*sign,'v':10*sign},self.params)
            self.assertIsNotNone(p);self.assertLessEqual(len(p),241)
            self.assertTrue(np.allclose(p[:,1],sign*p[:,0]*10,atol=1e-5))
            self.assertAlmostEqual(p[0,2],10);self.assertAlmostEqual(p[-1,2],10)
    def test_long_link_still_rejects_impossible_motion_and_excess_duration(self):
        self.assertIsNone(prediction({'t':0,'x':0,'v':10},{'t':180,'x':10000,'v':10},self.params))
        self.assertIsNone(prediction({'t':0,'x':0,'v':10},{'t':301,'x':3010,'v':10},self.params))
