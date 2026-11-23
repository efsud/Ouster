import unittest,numpy as np
from .kinematic_gate import path
class GateTests(unittest.TestCase):
    def test_exact_both_directions(self):
        for sign in (1,-1):
            a=dict(t=0,x=0,v=10*sign);b=dict(t=10,x=100*sign,v=10*sign)
            p=np.array(path(a,b,dict(vmax=30,amin=-6,amax=4)))
            self.assertAlmostEqual(p[-1,1],b['x'])
            self.assertTrue(np.all(np.diff(p[:,1])*sign>=0))
            acc=np.diff(p[:,2])/np.diff(p[:,0])
            self.assertTrue(np.all(acc>=-6-1e-8));self.assertTrue(np.all(acc<=4+1e-8))
    def test_impossible_remains_missing(self):
        self.assertIsNone(path(dict(t=0,x=0,v=0),dict(t=1,x=100,v=0),dict(vmax=30,amin=-6,amax=4)))
