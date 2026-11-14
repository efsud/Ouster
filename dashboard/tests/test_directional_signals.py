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
