import tempfile
from pathlib import Path
import unittest
from dashboard.live import snapshot
from dashboard.storage import Store

class LiveTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.store=Store(Path(self.tmp.name)/'live.sqlite')
        self.site={'id':'TEST','origin':{'lat':43,'lng':-79},'rotation_deg':180,'calibration_verified':True,'calibration':{'version':'fixture-1','reference':'Synthetic independent landmarks','landmarks':[{'x':0,'y':0,'lat':43,'lng':-79},{'x':10,'y':0,'lat':43,'lng':-79.00012284},{'x':0,'y':10,'lat':42.99991017,'lng':-79}]}}

    def tearDown(self): self.tmp.cleanup()

    def record(self,objects,stamp=100):
        self.store.save_event('TEST',stamp,{'frame':{'objects':objects}})

    def test_empty_current_frame_is_zero_not_missing(self):
        self.assertEqual(snapshot(self.store,self.site,100)['state'],'unavailable')
        self.record([])
        result=snapshot(self.store,self.site,100)
        self.assertEqual(result['state'],'live');self.assertEqual(result['objects'],[])

    def test_stale_and_future_clock_hide_objects(self):
        self.record([{'id':'car','centerX':10,'centerY':0}])
        for now in [106,94]:
            result=snapshot(self.store,self.site,now)
            self.assertEqual(result['state'],'stale');self.assertEqual(result['objects'],[])

    def test_calibration_required(self):
        self.record([{'id':'car','centerX':10}])
        self.site['calibration_verified']=False
        self.assertEqual(snapshot(self.store,self.site,100)['state'],'uncalibrated')
        self.site['calibration_verified']=True;del self.site['rotation_deg']
        self.assertEqual(snapshot(self.store,self.site,100)['state'],'uncalibrated')

    def test_invalid_object_does_not_drop_valid_frame(self):
        self.record([{'id':'good','centerX':10,'classType':'2'},{'id':'bad','centerX':float('nan')},{'centerX':0}])
        r=snapshot(self.store,self.site,100)
        self.assertEqual(r['state'],'live');self.assertEqual(len(r['objects']),1)
        self.assertEqual(r['rejected_objects'],2)
        self.assertLess(r['objects'][0]['lng'],-79)

    def test_sites_are_isolated_and_proto_defaults_preserved(self):
        self.record([{'id':'origin'}])
        r=snapshot(self.store,self.site,100)
        self.assertEqual([r['objects'][0]['lat'],r['objects'][0]['lng']],[43,-79])
        self.assertEqual(snapshot(self.store,dict(self.site,id='OTHER'),100)['state'],'unavailable')
