import unittest
from .object_shape import dimensions,summarize,discrepancy
class ShapeTests(unittest.TestCase):
    def test_missing_or_invalid_size_is_unavailable(self):
        self.assertIsNone(dimensions({}));self.assertIsNone(dimensions({'width':float('nan'),'length':4}))
        self.assertIsNone(summarize([None,[2,4]]))
    def test_axis_swap_and_median_are_robust(self):
        self.assertEqual(dimensions({'width':4,'length':2}),[2,4])
        d=summarize([[2,4],[2,4],[2,4],[3,9]])
        self.assertEqual(d['length_m'],4);self.assertEqual(discrepancy(d,d),0)
    def test_different_shape_is_only_soft_evidence(self):
        a=summarize([[2,4]]*5);b=summarize([[2.5,7]]*5)
        self.assertGreater(discrepancy(a,b),1);self.assertIsNone(discrepancy(a,None))
