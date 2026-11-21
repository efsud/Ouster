import unittest
import numpy as np
from audit_map_rotations import score

class RotationAuditTest(unittest.TestCase):
    def test_oneway_disambiguates_half_turn(self):
        # SDK +x movement must map north on a northbound segment.
        points=np.array([[0,20,0,1,0],[1,40,0,1,0]],float)
        a=np.array([[0,-100]],float);b=np.array([[0,100]],float)
        self.assertLess(score(points,a,b,90,oneway=np.array([1])),1e-6)
        self.assertGreater(score(points,a,b,270,oneway=np.array([1])),100)
    def test_two_way_axis_does_not_claim_direction(self):
        points=np.array([[0,20,0,1,0]],float);a=np.array([[0,-100]],float);b=np.array([[0,100]],float)
        self.assertAlmostEqual(score(points,a,b,90),score(points,a,b,270))
    def test_reflection_is_distinct_from_rotation(self):
        points=np.array([[0,20,-10,1,0]],float);a=np.array([[-100,10]],float);b=np.array([[100,10]],float)
        mirrored=points.copy();mirrored[:,[2,4]]*=-1
        self.assertLess(score(mirrored,a,b,0,oneway=np.array([1])),score(points,a,b,0,oneway=np.array([1])))
if __name__=='__main__':unittest.main()
