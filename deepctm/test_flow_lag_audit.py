import unittest,numpy as np
from .flow_lag_audit import profile
class FlowLagTests(unittest.TestCase):
    def test_known_aggregate_lag(self):
        rng=np.random.default_rng(12);a=rng.normal(size=300);b=np.r_[np.zeros(14),a[:-14]]
        self.assertEqual(profile(a,b,0,120)[0]['lag_s'],70)
    def test_constant_flow_has_no_lag_evidence(self):
        self.assertEqual(profile(np.ones(100),np.ones(100),0,60),[])
