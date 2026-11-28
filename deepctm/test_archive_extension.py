import unittest
import numpy as np
from .archive_extension import estimate,calibrated,features,cases
from .trajectory_reconstruction import baseline,refine

class ArchiveExtensionTests(unittest.TestCase):
    def setUp(self):
        self.a=dict(t=0.,x=0.,v=3.);self.b=dict(t=30.,x=60.,v=3.)
        self.params=dict(vmax=30.,amin=-4.,amax=3.)
        self.site={'station_m':0};self.track={'direction':'eastbound'}
        self.model=(np.tile(features(self.a,self.b,0),(5,1)),np.tile(np.sin(np.linspace(0,np.pi,41)),(5,1))*.1,np.ones(5))
    def test_zero_weight_reproduces_current(self):
        got,_=estimate(self.site,self.track,self.a,self.b,self.model,self.params,0)
        expected=refine(self.a,self.b,baseline(self.a,self.b),**self.params,smoothness=.01,position_tolerance=0,speed_tolerance=0)
        np.testing.assert_allclose(got['points'],expected['points'])
    def test_learned_shape_keeps_exact_joins(self):
        got,supported=estimate(self.site,self.track,self.a,self.b,self.model,self.params,.5)
        self.assertTrue(supported);self.assertEqual(got['state'],'candidate')
        np.testing.assert_allclose(got['points'][[0,-1],1:],[ [0,3],[60,3]],atol=1e-5)
    def test_matching_no_identity_or_order(self):
        left=[dict(t=0,x=0,v=10,class_type='2'),dict(t=20,x=0,v=10,class_type='2')]
        right=[dict(t=25,x=50,v=10,class_type='2'),dict(t=5,x=50,v=10,class_type='2')]
        pairs=calibrated(left,right,1,.25)
        self.assertEqual({(p['left'],p['right']) for p in pairs},{(0,1),(1,0)})
    def test_ambiguous_duplicates_remain_unmatched(self):
        a=dict(t=0,x=0,v=10,class_type='2');b=dict(t=5,x=50,v=10,class_type='2')
        self.assertEqual(calibrated([a,a],[b,b],1,.25),[])
if __name__=='__main__':unittest.main()
