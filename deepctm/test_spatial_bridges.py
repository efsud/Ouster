import unittest
import numpy as np
from .spatial_bridges import curve,associate
from .validate_spatial import masked

class SpatialTests(unittest.TestCase):
    def test_monotone_exact_endpoints_and_speed(self):
        a={'t':0,'x':0,'v':10};b={'t':10,'x':100,'v':10};p=curve(a,b)
        self.assertEqual(p[0][:2],[0,0]);self.assertEqual(p[-1][:2],[10,100]);self.assertTrue(all(abs(x[2]-10)<1e-8 for x in p))
    def test_westbound(self):
        p=curve({'t':0,'x':100,'v':-10},{'t':10,'x':0,'v':-10});self.assertTrue(all(b[1]<=a[1] for a,b in zip(p,p[1:])))
    def test_hidden_values_cannot_affect_boundary_inputs(self):
        tr={'direction':'eastbound','points':[[i*.5,i*2-100,4] for i in range(101)]};m=masked(tr,0,50)
        tr['points'][50][1]+=2;n=masked(tr,0,50)
        self.assertEqual(m[0],n[0]);self.assertEqual(m[1],n[1]);self.assertFalse(np.array_equal(m[2],n[2]))
    def test_ambiguous_matches_rejected(self):
        a={'t':0,'x':0,'v':10,'class_type':'1'};b={'t':10,'x':100,'v':10,'class_type':'1'}
        self.assertEqual(associate([a],[b,b]),[])
    def test_one_to_one(self):
        a=[{'t':t,'x':0,'v':10,'class_type':'1'} for t in [0,40]];b=[dict(x=100,t=e['t']+10,v=10,class_type='1') for e in a]
        m=associate(a,b);self.assertEqual([(r['left'],r['right']) for r in m],[(0,0),(1,1)])

    def test_queue_candidate_conserves_distance_and_has_stop(self):
        p=curve({'t':0,'x':0,'v':9},{'t':30,'x':100,'v':15},'queue')
        self.assertAlmostEqual(p[-1][1],100);self.assertAlmostEqual(p[0][2],9);self.assertAlmostEqual(p[-1][2],15)
        self.assertTrue(any(v==0 for t,x,v in p));self.assertTrue(all(b[1]>=a[1] for a,b in zip(p,p[1:])))
    def test_nonfinite_boundaries_rejected(self):
        self.assertIsNone(curve({'t':0,'x':float('nan'),'v':10},{'t':10,'x':100,'v':10}))
