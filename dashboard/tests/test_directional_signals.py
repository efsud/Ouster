import tempfile,unittest
from pathlib import Path
from dashboard.storage import Store
from dashboard.directional_signals import directional_snapshot

class DirectionalSignalTest(unittest.TestCase):
    def test_live_only_retains_absolute_deltas_and_expires(self):
        with tempfile.TemporaryDirectory() as t:
            store=Store(Path(t)/'db');site={'id':'S'}
            mapping={'directions':{'E':{'movement':'WE','verified':True,'evidence':'TEST FIXTURE','phase_numbers':['2']}}}
            def save(time,event,session='s'):
                store.save_preview([dict(site='S',session=session,received_at=time,status='received',event=event)])
                store.set_health('S',session=session)
            save(100,{'phaseChange':{'absolute':True,'phases':[{'phaseNumber':2,'status':1}]}})
            def east(now):return next(d for d in directional_snapshot(store,site,mapping,now)['directions'] if d['direction']=='E')
            self.assertEqual(east(101)['status'],'GREEN');self.assertEqual(east(106)['status'],'UNKNOWN')
            save(102,{'phaseChange':{'phases':[{'phaseNumber':2,'status':3}]}})
            save(103,{'frame':{'objects':[]}})
            self.assertEqual(east(104)['status'],'RED')
            self.assertEqual(store.availability('S')['count'],0)
            save(104,{'phaseChange':{'phases':[{'phaseNumber':2,'status':1}]}},'new')
            self.assertEqual(east(105)['status'],'UNKNOWN')
    def test_unverified_labels_never_become_colors(self):
        with tempfile.TemporaryDirectory() as t:
            store=Store(Path(t)/'db')
            result=directional_snapshot(store,{'id':'S'},{},100)
            self.assertEqual({d['direction']:d['movement'] for d in result['directions']},{'E':'WE','W':'EW','N':'SN','S':'NS'})
            self.assertTrue(all(d['status']=='UNKNOWN' for d in result['directions']))

    def test_estimated_colors_expire_and_remain_explicit(self):
        with tempfile.TemporaryDirectory() as t:
            store=Store(Path(t)/'db');site={'id':'S'}
            store.save_preview([dict(site='S',session='s',received_at=100,status='received',event={'phaseChange':{'absolute':True,'phases':[{'phaseNumber':2,'status':1}]}})])
            store.set_health('S',session='s')
            estimates={'updated_at':100,'sites':{'S':{'session':'s','last_receipt':100,'directions':{'E':{'accepted':True,'phase_numbers':['2']}}}}}
            def east(now):return next(d for d in directional_snapshot(store,site,{},now,estimates)['directions'] if d['direction']=='E')
            self.assertEqual(east(101)['status'],'GREEN')
            self.assertTrue(east(101)['estimated'])
            self.assertEqual(east(101)['confidence'],'provisional')
            from unittest.mock import patch
            with patch('dashboard.directional_signals.check_definition',return_value={'conflict':True}):
                self.assertEqual(east(101)['status'],'UNKNOWN')
                self.assertIn('conflicts',east(101)['reason'])
            self.assertEqual(east(106)['status'],'UNKNOWN')
            estimates['sites']['S']['session']='wrong'
            self.assertEqual(east(101)['status'],'UNKNOWN')

    def test_phase_panel_is_independent_of_direction_mapping(self):
        with tempfile.TemporaryDirectory() as t:
            store=Store(Path(t)/'db')
            store.save_preview([dict(site='S',session='s',received_at=100,status='received',event={'phaseChange':{'absolute':True,'phases':[{'phaseNumber':2,'status':1},{'phaseNumber':64,'status':0}]}})])
            store.set_health('S',session='s')
            data=directional_snapshot(store,{'id':'S'},{},101)
            self.assertEqual([p['status'] for p in data['phases']],['GREEN','INVALID'])
            self.assertTrue(all(d['status']=='UNKNOWN' for d in data['directions']))
            stale=directional_snapshot(store,{'id':'S'},{},106)
            self.assertTrue(all(p['status']=='UNKNOWN' for p in stale['phases']))
