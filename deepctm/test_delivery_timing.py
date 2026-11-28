import json,unittest
from datetime import datetime,timedelta
from .delivery_timing import correct

class DeliveryTimingTests(unittest.TestCase):
    def rows(self,delay=True):
        rows=[]
        for i in range(300):
            # Delayed delivery then catch-up without dropping captured frames.
            arrival=1000+i*.1+(max(0,5-(i-80)*.05) if delay and 80<=i<180 else 0)
            stamp=(datetime(2026,1,1)+timedelta(seconds=i*.1)).isoformat()
            rows.append(('session',arrival,json.dumps({'timestamp':stamp,'frame':{'objects':[{'id':i}]}})))
        return rows
    def test_recovers_clock_interval_preserves_payloads_receipts_and_anchors(self):
        rows=self.rows();out,audit=correct(rows)
        self.assertGreater(audit[0]['corrected_frames'],0)
        self.assertEqual([(r[0],r[3],r[2]) for r in out],rows)
        self.assertLess(max(abs(r[1]-(1000+i*.1)) for i,r in enumerate(out)),.1)
        self.assertEqual(out[0][1],rows[0][1]);self.assertEqual(out[-1][1],rows[-1][1])
    def test_real_frame_loss_is_not_filled(self):
        rows=self.rows(False);rows=rows[:80]+rows[130:]
        out,audit=correct(rows)
        self.assertEqual([r[1] for r in out],[r[1] for r in rows]);self.assertEqual(len(out),len(rows))
    def test_bad_clock_or_no_return_anchor_keeps_receipts(self):
        for variant in ('duplicate','reset','no_anchor'):
            rows=self.rows()
            if variant=='no_anchor':rows=rows[:150]
            else:
                k=100;stamp=json.loads(rows[k-1 if variant=='duplicate' else 0][2])['timestamp']
                rows[k]=(rows[k][0],rows[k][1],json.dumps({'timestamp':stamp}))
            out,audit=correct(rows)
            self.assertEqual([r[1] for r in out],[r[1] for r in rows],variant)
    def test_no_join_between_sessions(self):
        rows=self.rows();rows=[(('other' if i>=120 else r[0]),r[1],r[2]) for i,r in enumerate(rows)]
        out,audit=correct(rows);self.assertTrue(all(x['corrected_frames']==0 for x in audit))
