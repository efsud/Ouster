import unittest
import numpy as np
from .lateral_gap import lateral_curve,supports

class LateralGapTests(unittest.TestCase):
    def fragments(self,dy=3.5):
        return {'lateral_end_context':[[t,0] for t in [-2,-1.5,-1,-.5,0]]},{'lateral_start_context':[[t,dy] for t in [10,10.5,11,11.5,12]]}
    def test_smooth_lane_change_and_exact_endpoints(self):
        a,b=self.fragments();p,e=lateral_curve(a,b,np.linspace(0,10,21))
        self.assertIsNotNone(p);self.assertEqual(p[0,1],0);self.assertEqual(p[-1,1],3.5)
        self.assertEqual(e['lane_change'],'estimated_not_verified')
        ok,_=supports(a,b,[[t,t*10,10] for t in np.linspace(0,10,21)]);self.assertTrue(ok)
    def test_wide_jump_and_missing_context_rejected(self):
        a,b=self.fragments(9);self.assertIsNone(lateral_curve(a,b,np.linspace(0,10,21))[0])
        self.assertIsNone(lateral_curve({},b,np.linspace(0,10,21))[0])
    def test_road_exit_rejected(self):
        a,b=self.fragments();a['lateral_end_context']=[[t,17] for t,_ in a['lateral_end_context']];b['lateral_start_context']=[[t,20.5] for t,_ in b['lateral_start_context']]
        self.assertIsNone(lateral_curve(a,b,np.linspace(0,10,21))[0])
