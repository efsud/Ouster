import unittest
import numpy as np
from .adaptive_endpoint_grid import envelope_grid,retry
from .feasible_seed import velocity_seed
from .trajectory_reconstruction import grid,integrate_matrix,refine,baseline

class AdaptiveGridTests(unittest.TestCase):
    def test_short_terminal_acceleration_is_representable(self):
        a={'t':0.,'x':0.,'v':0.};b={'t':10.,'x':.02,'v':.107}
        params={'vmax':25.,'amin':-4.,'amax':3.}
        self.assertIsNone(velocity_seed(a,b,grid(a,b),**params))
        t=envelope_grid(a,b,params);v=velocity_seed(a,b,t,**params)
        self.assertIsNotNone(v)
        A,D=integrate_matrix(t)
        self.assertAlmostEqual((A@v)[-1],.02)
        self.assertLessEqual(max(D@v),3.+1e-8)
        self.assertGreaterEqual(min(D@v),-4.-1e-8)

    def test_true_impossibility_stays_rejected(self):
        a={'t':0.,'x':0.,'v':10.};b={'t':10.,'x':1.,'v':0.}
        params={'vmax':25.,'amin':-4.,'amax':3.}
        self.assertIsNone(velocity_seed(a,b,envelope_grid(a,b,params),**params))

    def test_invalid_custom_grid_rejected(self):
        a={'t':0.,'x':0.,'v':1.};b={'t':10.,'x':10.,'v':1.}
        with self.assertRaises(ValueError):refine(a,b,baseline(a,b),time_grid=[0,5,5,10])
