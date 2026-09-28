import tempfile
import unittest
from pathlib import Path
from dashboard.storage import Store
from dashboard.live import approximate_snapshot,snapshot

class PreviewTest(unittest.TestCase):
    def test_quarantined_receipts_are_only_approximate_and_expire(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(Path(tmp)/'db');site={'id':'S','reference_location':{'lat':43.75,'lng':-79.52}}
            def save(objects):
                store.save_batch([dict(site='S',session='a',received_at=100,sensor_time=None,status='quarantined',reason='unknown_timezone',event={'timestamp':'2026-09-28T20:00:00','frame':{'objects':objects}})])
            save([{'id':'1','centerX':10,'centerY':0,'classType':'2'}])
            a=approximate_snapshot(store,site,101,180)
            self.assertEqual(a['state'],'approximate');self.assertLess(a['objects'][0]['lng'],-79.52)
            self.assertEqual(snapshot(store,site,101)['objects'],[])
            self.assertEqual(approximate_snapshot(store,site,106)['objects'],[])
            save([]);self.assertEqual(approximate_snapshot(store,site,101)['objects'],[])
    def test_invalid_clock_never_enters_preview(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(Path(tmp)/'db')
            store.save_batch([dict(site='S',session='a',received_at=100,sensor_time=None,status='quarantined',reason='invalid_timestamp',event={'frame':{'objects':[]}})])
            self.assertEqual(approximate_snapshot(store,{'id':'S'},101)['state'],'unavailable')
