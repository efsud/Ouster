import tempfile
import unittest
from pathlib import Path
from dashboard.storage import Store
from dashboard.collector import persist_observations

class RecordingWindowTest(unittest.TestCase):
    def test_history_stops_at_boundary_but_live_continues(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Store(Path(tmp)/'db')
            def row(t):return dict(site='S',session='a',received_at=t,sensor_time=t,status='received',event={'timestamp':str(t),'frame':{'objects':[]}})
            self.assertEqual(persist_observations(db,[row(99),row(100),row(101)],100),1)
            self.assertEqual(db.availability('S')['count'],1)
            self.assertEqual(db.latest('S')['timestamp'],101)
            self.assertEqual(persist_observations(db,[row(102)],100),0)
            self.assertEqual(db.availability('S')['count'],1)
            self.assertEqual(db.latest('S')['timestamp'],102)
            summary=db.recorded_summary('S')
            self.assertEqual(summary['events'],1)
            self.assertEqual(summary['end'],99)
            self.assertEqual(summary['buckets'][0]['events'],1)
    def test_live_only_keeps_quarantined_preview_without_raw_growth(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Store(Path(tmp)/'db')
            r=dict(site='S',session='a',received_at=101,sensor_time=None,status='quarantined',reason='unknown_timezone',event={'timestamp':'no offset','frame':{'objects':[]}})
            self.assertEqual(persist_observations(db,[r],0),0)
            self.assertEqual(db.availability('S')['count'],0)
            with db.connect() as c:self.assertEqual(c.execute('SELECT received_at FROM preview_frames').fetchone()[0],101)
