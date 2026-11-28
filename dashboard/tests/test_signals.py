import tempfile
import unittest
from pathlib import Path
from dashboard.signals import apply_change,SignalReader
from dashboard.storage import Store

class SignalTest(unittest.TestCase):
    def test_absolute_replaces_and_delta_preserves(self):
        s={};apply_change(s,'a',{'absolute':True,'phases':[{'phaseNumber':'1','status':1},{'phaseNumber':'2','status':3}]},1)
        apply_change(s,'a',{'phases':[{'phaseNumber':'1','status':2}]},2)
        self.assertEqual(s['phases']['2']['status'],'RED');self.assertEqual(s['phases']['1']['status'],'YELLOW')
        apply_change(s,'a',{'absolute':True,'phases':[]},3)
        self.assertEqual(s['phases'],{});self.assertTrue(s['initialized'])
    def test_session_reset_defaults_and_timestamp_regression(self):
        s={};apply_change(s,'a',{'absolute':True,'phases':[{'phaseNumber':'1','status':1,'timestamp':'2026-09-29T10:00:02'}]},1)
        apply_change(s,'a',{'phases':[{'phaseNumber':'1','status':3,'timestamp':'2026-09-29T10:00:01'}]},2)
        self.assertEqual(s['phases']['1']['status'],'GREEN')
        apply_change(s,'b',{'phases':[{'phaseNumber':'2'}]},3)
        self.assertFalse(s['initialized']);self.assertNotIn('1',s['phases']);self.assertEqual(s['phases']['2']['status'],'INVALID')
    def test_stale_receipts_and_partial_state_are_unconfirmed(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(Path(tmp)/'db');store.set_health('S',session='a',state='receiving')
            def save(t,change):
                store.save_batch([dict(site='S',session='a',received_at=t,sensor_time=None,status='quarantined',reason='unknown_timezone',event={'timestamp':str(t),'phaseChange':change})])
            save(100,{'phases':[{'phaseNumber':'1','status':1}]})
            reader=SignalReader(store)
            self.assertEqual(reader.snapshot('S',101)['phases'][0]['display_status'],'UNCONFIRMED')
            save(102,{'absolute':True,'phases':[{'phaseNumber':'1','status':3}]})
            self.assertEqual(reader.snapshot('S',103)['phases'][0]['display_status'],'RED')
            self.assertEqual(reader.snapshot('S',109)['phases'][0]['display_status'],'UNCONFIRMED')
            save(110,{'phases':[{'phaseNumber':'2','status':1}]})
            r=reader.snapshot('S',111)
            self.assertFalse(r['absolute_received']);self.assertEqual([p['phase'] for p in r['phases']],['2'])
