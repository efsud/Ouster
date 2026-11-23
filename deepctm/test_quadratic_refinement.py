import unittest,importlib.util
import numpy as np
from .quadratic_refinement import solve,terms
from .trajectory_reconstruction import baseline,grid,integrate_matrix

@unittest.skipUnless(importlib.util.find_spec('osqp'),'optional experimental OSQP dependency')
class QuadraticTests(unittest.TestCase):
    params={'vmax':25.,'amin':-4.,'amax':3.}
    def test_constant_speed_and_endpoints(self):
        a={'t':0.,'x':1000.,'v':10.};b={'t':10.,'x':1100.,'v':10.}
        r=solve(a,b,self.params);self.assertEqual(r['state'],'candidate')
        np.testing.assert_allclose(r['points'][:,2],10.,atol=1e-4)
        self.assertAlmostEqual(r['points'][-1,1],1100.,places=5)
    def test_infeasible_does_not_relax(self):
        r=solve({'t':0.,'x':0.,'v':10.},{'t':10.,'x':1.,'v':0.},self.params)
        self.assertEqual(r['state'],'infeasible')
    def test_quadratic_matches_original_loss_difference(self):
        a={'t':0.,'x':2.,'v':3.};b={'t':10.,'x':52.,'v':7.};t=grid(a,b);ref=baseline(a,b)
        P,q,A,D=terms(a,b,ref,self.params,t);J=np.diff(D,axis=0);n=len(t)
        def loss(v):
            err=(A@v-(ref[:,1]-a['x']))/50.;dv=(v-ref[:,2])/25.;jerk=J@v
            return err@err/n+.05*(dv@dv)/n+.01*(jerk@jerk)/len(J)
        x=np.linspace(3,7,n);y=np.linspace(2,8,n)
        self.assertAlmostEqual(loss(x)-loss(y),.5*x@P@x+q@x-.5*y@P@y-q@y,places=10)
    def test_adaptive_grid_preserves_small_displacement(self):
        a={'t':0.,'x':0.,'v':0.};b={'t':10.,'x':.02,'v':.107}
        self.assertEqual(solve(a,b,self.params)['state'],'infeasible')
        r=solve(a,b,self.params,adaptive=True)
        self.assertEqual(r['state'],'candidate');self.assertAlmostEqual(r['points'][-1,1],.02,places=5)
