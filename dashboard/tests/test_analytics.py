import copy
import tempfile
from pathlib import Path
import unittest
from dashboard.analytics import calculate, local_to_geo, simulate
from dashboard.demo import generate
from dashboard.storage import Store

def fixture():
    return {'start':0,'end':300,'length_m':100,'free_speed_mps':10,'lanes':2,'coverage':1,
        'signal_synchronized':True,'entry_observation_complete':True,'departure_observation_complete':True,'green_seconds':150,
        'tracks':[{'id':str(i),'vehicle':True,'entry':i*10,'arrival':i*10+30,'exit':i*10+32,'complete':True,'max_gap_s':1,'stopped_s':12,'green':i%2==0,'departed_from_queue_on_green':True} for i in range(20)],
        'queue_samples':[{'time':i*5,'length_m':i,'visible':True} for i in range(60)],
        'cycles':[{'start':0,'end':90,'visible':True,'residual_queue_m':5},{'start':90,'end':180,'visible':True,'residual_queue_m':0}]}

class KPITest(unittest.TestCase):
    def test_known_values_and_lane_normalization(self):
        r=calculate(fixture())
        self.assertEqual(r['values'],{'control_delay':20,'stopped_delay':12,'queue_p95':56.05,'aog':50,'split_failure':50,'volume':240,'discharge':240})
        self.assertEqual(r['quality']['status'],'passes-input-checks')

    def test_censored_track_can_count_entry_but_not_delay(self):
        w=fixture();w['tracks'][0]['complete']=False
        r=calculate(w)
        self.assertEqual(r['quality']['valid_tracks'],19)
        self.assertEqual(r['values']['volume'],240)

    def test_gap_and_nonvehicle_exclusion(self):
        w=fixture();w['tracks'][0]['max_gap_s']=3.01;w['tracks'][1]['vehicle']=False
        r=calculate(w)
        self.assertEqual(r['quality']['valid_tracks'],18)
        self.assertEqual(r['values']['volume'],216)

    def test_unknown_signal_not_zero(self):
        w=fixture();w['signal_synchronized']=False
        r=calculate(w)['values']
        self.assertIsNone(r['aog']);self.assertIsNone(r['split_failure']);self.assertIsNone(r['discharge'])
        w=fixture();del w['tracks'][0]['green']
        self.assertIsNone(calculate(w)['values']['aog'])

    def test_no_observations_not_zero_and_observed_empty_zero(self):
        w=fixture();w['tracks']=[];w['queue_samples']=[];w['cycles']=[]
        v=calculate(w)['values']
        self.assertIsNone(v['control_delay']);self.assertIsNone(v['queue_p95']);self.assertEqual(v['volume'],0)
        w['entry_observation_complete']=False
        self.assertIsNone(calculate(w)['values']['volume'])
        w['queue_samples']=[{'time':0,'length_m':0,'visible':True}]
        self.assertEqual(calculate(w)['values']['queue_p95'],0)

    def test_half_open_window(self):
        w=fixture();w['tracks'][0].update(entry=300,arrival=330,exit=332)
        r=calculate(w);self.assertEqual(r['quality']['valid_tracks'],19);self.assertEqual(r['values']['volume'],228)

    def test_reject_invalid_and_duplicate(self):
        for key,value in [('end',0),('coverage',1.5),('lanes',1.5),('free_speed_mps',0),('green_seconds',400)]:
            w=fixture();w[key]=value
            with self.assertRaises(ValueError):calculate(w)
        w=fixture();w['tracks'].append(w['tracks'][0])
        with self.assertRaises(ValueError):calculate(w)

    def test_quality_does_not_hide_provisional_values(self):
        w=fixture();w['coverage']=.6;w['tracks']=w['tracks'][:2]
        r=calculate(w)
        self.assertEqual(r['quality']['status'],'provisional');self.assertEqual(r['values']['control_delay'],20)

class CTMTest(unittest.TestCase):
    def test_conservation_and_bounds(self):
        for demand in [0,900,2400]:
            for green in [0,45,90]:
                r=simulate({'demand':demand,'green':green,'intersections':7})
                self.assertAlmostEqual(r['conservation_error'],0,places=8)
                self.assertAlmostEqual(r['admitted']+r['backlog'],demand*900/3600,places=8)
                self.assertGreaterEqual(r['remaining'],-1e-8)
                for frame in r['history']:
                    self.assertTrue(all(0<=d<=150 for d in frame['density']))

    def test_red_holds_traffic_and_green_releases(self):
        red=simulate({'green':0});green=simulate({'green':90})
        self.assertEqual(red['departed'],0);self.assertGreater(green['departed'],0)
        self.assertGreater(red['backlog'],green['backlog'])

    def test_reject_bad_parameters(self):
        for params in [{'green':100},{'demand':float('nan')},{'intersections':1.5},{'intersections':0}]:
            with self.assertRaises(ValueError):simulate(params)

class CoordinateTest(unittest.TestCase):
    def test_origin_and_rotation(self):
        self.assertEqual(local_to_geo(0,0,43,-79,180),[43,-79])
        self.assertGreater(local_to_geo(100,0,43,-79,0)[1],-79)
        self.assertLess(local_to_geo(100,0,43,-79,180)[1],-79)
        self.assertGreater(local_to_geo(100,0,43,-79,90)[0],43)

class StorageTest(unittest.TestCase):
    def test_persistence_filter_and_idempotency(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'test.db';s=Store(path);demo=generate()
            s.save_windows(demo);s.save_windows(demo)
            self.assertEqual(len(Store(path).history(site='DEMO-001')),36)
            self.assertEqual(s.history(site='TORONTO'),[])
            s.save_event('X',100,{'frame':{'objects':[]}})
            self.assertEqual(s.latest('X')['timestamp'],100)

if __name__=='__main__':unittest.main()
