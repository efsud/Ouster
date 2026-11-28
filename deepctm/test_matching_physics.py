import unittest
from .matching_physics import reachability,associate
from .spatial_bridges import associate as old

class PhysicsTests(unittest.TestCase):
    params={'vmax':25.,'amin':-6.,'amax':4.}
    def ep(self,t,x,v):return dict(t=t,x=x,v=v,class_type='2')
    def test_constant_motion_in_both_directions(self):
        for sign in (1,-1):self.assertIsNone(reachability(self.ep(0,0,10*sign),self.ep(10,100*sign,10*sign),self.params))
    def test_high_endpoint_and_impossible_arrival_rejected(self):
        self.assertEqual(reachability(self.ep(0,0,26),self.ep(10,100,10),self.params),'endpoint_speed_bound')
        self.assertIsNotNone(reachability(self.ep(0,0,10),self.ep(1,100,10),self.params))
    def test_impossible_short_distance_rejected(self):
        self.assertEqual(reachability(self.ep(0,0,20),self.ep(1,2,20),self.params),'too_little_distance_for_endpoint_speeds')
    def test_ambiguity_preserved(self):
        a=self.ep(0,0,10);b=self.ep(5,50,10)
        self.assertEqual(associate([a,a],[b,b],self.params),[])
    def test_long_finch_link_is_explicit_and_physical(self):
        a=self.ep(0,0,15);b=self.ep(40,600,15)
        self.assertEqual(associate([a],[b],self.params),[])
        self.assertEqual(len(associate([a],[b],self.params,max_distance=3000)),1)
        self.assertEqual(associate([a],[self.ep(5,600,15)],self.params,max_distance=3000),[])
    def test_exact_gate_does_not_change_normal_unique_pair(self):
        a=self.ep(0,0,10);b=self.ep(5,50,10)
        before=old([a],[b],method='feasible');after=associate([a],[b],self.params)
        self.assertEqual([(m['left'],m['right']) for m in before],[(m['left'],m['right']) for m in after])
if __name__=='__main__':unittest.main()
