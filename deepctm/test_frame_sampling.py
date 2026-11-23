import unittest
from .frame_sampling import sample
class SamplingTests(unittest.TestCase):
    def test_preserves_actual_rows_and_gaps(self):
        rows=[('s',t,'payload') for t in (0,.1,.2,.6,5,5.1,5.6)]
        result=sample(rows,.5)
        self.assertEqual([r[1] for r in result],[0,.6,5,5.6])
        self.assertTrue(all(row in rows for row in result))
    def test_sessions_independent(self):
        rows=[('a',0),('b',.1),('a',.2),('b',.6)]
        self.assertEqual(sample(rows,.5),[rows[0],rows[1],rows[3]])
    def test_zero_and_invalid(self):
        rows=[('s',0),('s',.1)];self.assertEqual(sample(rows,0),rows)
        for v in (-1,float('nan')):
            with self.assertRaises(ValueError):sample(rows,v)
