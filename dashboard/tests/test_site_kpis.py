import tempfile
import unittest
from pathlib import Path
from dashboard.storage import Store
from dashboard.site_kpis import summary
from dashboard.analytics import METRICS

class SiteKPITest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=Store(Path(self.tmp.name)/'db');self.site={'id':'S','name':'Test intersection'}
    def tearDown(self):self.tmp.cleanup()
    def save(self,site='S',approach='NB',source='sdk-derived',start=0,end=300,value=12):
        window=dict(site=site,approach=approach,source=source,start=start,end=end)
        result={'values':{k:value for k in METRICS},'quality':{'valid_tracks':20,'coverage':.9,'flags':[],'status':'passes-input-checks'}}
        self.store.save_windows([(window,result)])
    def test_empty_site_shows_all_seven_without_zero_values(self):
        data=summary(self.store,self.site)
        self.assertEqual(len(data['metrics']),7)
        self.assertTrue(all(m['value'] is None and m['reasons'] for m in data['metrics']))
    def test_synthetic_and_other_sites_never_leak(self):
        self.save(source='synthetic');self.save(site='OTHER')
        data=summary(self.store,self.site)
        self.assertEqual(data['windows'],[]);self.assertTrue(all(m['value'] is None for m in data['metrics']))
    def test_approach_and_window_selection_preserves_saved_values(self):
        self.save(value=12);self.save(start=300,end=600,value=24);self.save(approach='SB',value=99)
        data=summary(self.store,self.site,'NB')
        self.assertEqual(data['metrics'][0]['value'],24)
        old=summary(self.store,self.site,'NB',data['windows'][1]['key'])
        self.assertEqual(old['metrics'][0]['value'],12)
        self.assertEqual(old['selected_window']['quality']['coverage'],.9)
    def test_daily_discharge_suppressed_and_raw_quarantine_explained(self):
        self.store.save_batch([dict(site='S',session='a',received_at=1,sensor_time=None,status='quarantined',reason='unknown_timezone',event={'frame':{'objects':[]}})])
        data=summary(self.store,self.site)
        self.assertTrue(any('timezone' in r for r in data['metrics'][0]['reasons']))
        self.save(end=86400)
        data=summary(self.store,self.site)
        self.assertIsNone(next(m for m in data['metrics'] if m['id']=='discharge')['value'])
