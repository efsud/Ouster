import unittest
from datetime import datetime,timedelta
from .event_clock import align
class EventClockTests(unittest.TestCase):
    def rows(self):
        base=datetime(2026,1,1)
        return [(1000+i,(base+timedelta(seconds=i)).isoformat()) for i in range(200)]
    def test_burst_delays_do_not_change_sensor_elapsed_motion(self):
        rows=self.rows();rows[80]=(rows[80][0]+3,rows[80][1]);r=align(rows)
        self.assertEqual(r['state'],'candidate');self.assertAlmostEqual(r['times'][81]-r['times'][80],1)
        self.assertGreater(r['receipt_residual_max_s'],2)
    def test_clock_reset_and_rate_drift_rejected(self):
        rows=self.rows();rows[100]=(rows[100][0],rows[0][1]);self.assertEqual(align(rows)['state'],'unavailable')
        self.assertEqual(align([(t*2,s) for t,s in self.rows()])['state'],'unavailable')
    def test_timezone_offset_is_not_asserted(self):
        rows=self.rows();r=align([(t,s+'+05:00') for t,s in rows]);base=align(rows)
        self.assertEqual(r['times'],base['times']);self.assertTrue(r['retrospective_only'])
    def test_short_sample_is_not_aligned(self):
        self.assertEqual(align(self.rows()[:10])['state'],'unavailable')
