import tempfile
import unittest
from pathlib import Path
from dashboard.storage import Store
from dashboard.live import approximate_snapshot,snapshot

class PreviewTest(unittest.TestCase):
    def test_site_rotation_and_origin_with_explicit_override(self):
        from dashboard.analytics import local_to_geo
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(Path(tmp)/'db')
            for ident,rotation,lat,lng in [('A',140,43.736772,-79.591825),('B',145,43.741152,-79.589252),('C',220,43.743273,-79.582284),('D',210,43.746175,-79.568791),('E',135,43.753306,-79.536397)]:
                site={'id':ident,'reference_location':{'lat':lat,'lng':lng},'preview_rotation_deg':rotation}
                store.save_batch([dict(site=ident,session='a',received_at=100,sensor_time=None,status='quarantined',reason='unknown_timezone',event={'frame':{'objects':[{'id':'origin'},{'id':'offset','centerX':10,'centerY':5}]}})])
                for override in [None,220]:
                    r=approximate_snapshot(store,site,101,override)
                    angle=rotation if override is None else override
                    self.assertEqual(r['rotation_deg'],angle)
                    self.assertEqual((r['objects'][0]['lat'],r['objects'][0]['lng']),(lat,lng))
                    expected=local_to_geo(10,5,lat,lng,angle)
                    self.assertEqual((r['objects'][1]['lat'],r['objects'][1]['lng']),tuple(expected))
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
