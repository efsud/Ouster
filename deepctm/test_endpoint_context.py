import unittest
from .endpoint_context import select
from .spatial_bridges import endpoint
class ContextTests(unittest.TestCase):
    def test_low_rate_unchanged(self):
        p=[[i*.5,i*5,10] for i in range(30)]
        self.assertEqual(select(p,True),p[-5:]);self.assertEqual(select(p,False),p[:5])
    def test_dense_visible_context_retains_speed(self):
        p=[[i*.1,i,10] for i in range(30)]
        for side in (False,True):
            ep=endpoint(p,side)
            self.assertIsNotNone(ep);self.assertAlmostEqual(ep['v'],10)
            self.assertGreaterEqual(ep['velocity_evidence']['duration_s'],1)
    def test_short_and_discontinuous_remain_unavailable(self):
        self.assertIsNone(endpoint([[i*.1,i,10] for i in range(8)],False))
        self.assertIsNone(endpoint([[0,0,0],[.1,1,0],[.2,2,0],[.3,3,0],[4,4,0]],False))
