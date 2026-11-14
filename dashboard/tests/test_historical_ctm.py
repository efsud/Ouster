import unittest
from datetime import datetime,timezone
from dashboard.historical_ctm import parameters,inputs,model

class HistoricalCTMTest(unittest.TestCase):
    def event(self,t,x,session='s',ident='1'):
        return dict(received_at=t,session=session,status='quarantined',reason='unknown_timezone',payload={'timestamp':datetime.fromtimestamp(t,timezone.utc).isoformat(),'frame':{'objects':[dict(id=ident,classType='1',centerX=x,centerY=0)]}})
    def test_crossings_not_messages_and_session_namespace(self):
        records=[self.event(1,-1),self.event(2,1),self.event(3,-1),self.event(4,1),self.event(5,-1,'new'),self.event(6,1,'new')]
        b,n=inputs(records,0,300,parameters({}))
        self.assertEqual(n,6);self.assertEqual(b[0]['crossings'],2)
    def test_gaps_missing_coordinates_and_censored_tracks(self):
        records=[self.event(1,1),self.event(2,-1),self.event(6,1),self.event(7,-1)]
        r=self.event(8,1);del r['payload']['frame']['objects'][0]['centerY'];records.append(r)
        b,_=inputs(records,0,300,parameters({}));self.assertEqual(b[0]['crossings'],0)
    def test_conservation_and_signal_sensitivity(self):
        bins=[dict(start=i*300,end=(i+1)*300,coverage=1,crossings=100) for i in range(12)]
        green,e=model(bins,parameters({'green_s':90}));red,e2=model(bins,parameters({'green_s':0}))
        self.assertLess(max(e,e2),1e-8)
        self.assertGreater(sum(r['model_departed'] for r in green),0)
        self.assertEqual(sum(r['model_departed'] for r in red),0)
        self.assertTrue(all(r['values']['aog'] is None and r['values']['stopped_delay'] is None for r in green))
    def test_outage_is_gap_and_reinitializes_model(self):
        bins=[dict(start=i*300,end=(i+1)*300,coverage=coverage,crossings=20) for i,coverage in enumerate([1,.1,1])]
        rows,_=model(bins,parameters({}))
        self.assertTrue(all(v is None for v in rows[1]['values'].values()))
        self.assertTrue(any('warm-up' in f for f in rows[2]['flags']))
    def test_parameters_reject_bad_values(self):
        for p in [{'lanes':1.2},{'axis':'z'},{'green_s':100},{'free_speed_mps':float('nan')}]:
            with self.assertRaises(ValueError):parameters(p)
    def test_archive_range_supports_day_and_rejects_longer(self):
        import tempfile
        from pathlib import Path
        from dashboard.storage import Store
        from dashboard.historical_ctm import analyze
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(Path(tmp)/'archive.sqlite')
            store.save_batch([dict(site='S',session='s',received_at=1,sensor_time=None,status='quarantined',reason='unknown_timezone',event={'frame':{'objects':[]}})])
            result=analyze(store,'S',0,86400,{})
            self.assertEqual(len(result['rows']),288)
            self.assertTrue(all(r['values']['volume'] is None for r in result['rows']))
            with self.assertRaises(ValueError):analyze(store,'S',0,86401,{})
    def test_recording_status_requires_recent_saved_event(self):
        import tempfile,time
        from pathlib import Path
        from dashboard.storage import Store
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(Path(tmp)/'archive.sqlite')
            store.set_health('S',recording_mode='recording')
            self.assertFalse(store.availability('S')['recording_active'])
            store.save_batch([dict(site='S',session='s',received_at=time.time(),sensor_time=None,status='quarantined',reason='unknown_timezone',event={'frame':{'objects':[]}})])
            self.assertTrue(store.availability('S')['recording_active'])
            store.set_health('S',recording_mode='live_only')
            self.assertFalse(store.availability('S')['recording_active'])
