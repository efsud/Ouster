import unittest
import numpy as np
from .feasible_seed import velocity_seed,retry
from .trajectory_reconstruction import baseline,grid,integrate_matrix

class FeasibleSeedTests(unittest.TestCase):
    def test_random_feasible_integrals_and_acceleration(self):
        rng=np.random.default_rng(93)
        for _ in range(100):
            t=np.linspace(0,30,61);v=np.clip(10+np.cumsum(rng.uniform(-.2,.2,len(t))),0,30)
            A,D=integrate_matrix(t);a={'t':0,'x':0,'v':v[0]};b={'t':30,'x':float(A[-1]@v),'v':v[-1]}
            seed=velocity_seed(a,b,t,30,-4,3)
            self.assertIsNotNone(seed);self.assertAlmostEqual(A[-1]@seed,b['x'],places=7)
            self.assertTrue(np.all(D@seed>=-4-1e-8));self.assertTrue(np.all(D@seed<=3+1e-8))
            self.assertAlmostEqual(seed[0],a['v']);self.assertAlmostEqual(seed[-1],b['v'])
    def test_impossible_distance_and_reverse_are_not_repaired(self):
        a={'t':0,'x':0,'v':10};b={'t':1,'x':100,'v':10};t=grid(a,b)
        self.assertIsNone(velocity_seed(a,b,t,30,-4,3))
        self.assertIsNone(velocity_seed(dict(a,v=-.1),dict(b,x=10),t,30,-4,3))
    def test_successful_strict_result_unchanged(self):
        a={'t':0,'x':0,'v':10};b={'t':10,'x':100,'v':10}
        r,changed=retry(a,b,baseline(a,b),{'vmax':30,'amin':-4,'amax':3})
        self.assertFalse(changed);self.assertEqual(r['state'],'candidate')
