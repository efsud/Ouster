import unittest
from datetime import datetime,timedelta
from .local_tracklet_matching import candidate,reconstruct

def track(identifier,start,finish,lateral=0):
    zero=datetime(2026,1,1)
    return dict(source_key=['session',identifier,'2'],class_type='2',direction='eastbound',movement={'movement':'WE'},
        points=[[t/2,5*t,10] for t in range(int(2*start),int(2*finish)+1)],
        lateral_start_m=lateral,lateral_end_m=lateral,
        sensor_start=(zero+timedelta(seconds=start)).isoformat(),sensor_end=(zero+timedelta(seconds=finish)).isoformat())

class LocalTrackletTests(unittest.TestCase):
    def test_supported_changed_id(self):
        a,b=track('a',0,3),track('b',8,11)
        self.assertIsNotNone(candidate(a,b))
        r=reconstruct({'id':'site','tracks':[a,b]},lambda a,b:[[a['t'],a['x'],a['v']],[b['t'],b['x'],b['v']]])
        self.assertEqual(len(r),1);self.assertEqual(r[0]['identity'],'unverified_same_site_changed_id')
    def test_ambiguous_parallel_tracks_not_joined(self):
        tracks=[track('a',0,3),track('b',8,11),track('c',8,11)]
        self.assertEqual(reconstruct({'id':'site','tracks':tracks},lambda a,b:[[a['t'],a['x'],10],[b['t'],b['x'],10]]),[])
    def test_movement_lateral_clock_and_session_gates(self):
        a=track('a',0,3)
        for b in [track('b',8,11,4),dict(track('b',8,11),movement={'movement':'WN'}),dict(track('b',8,11),source_key=['other','b','2']),dict(track('b',8,11),sensor_start='2026-01-02')]:
            self.assertIsNone(candidate(a,b))
    def test_existing_local_endpoints_not_reused(self):
        self.assertEqual(reconstruct({'id':'site','tracks':[track('a',0,3),track('b',8,11)]},lambda a,b:[],[(3,9)]),[])
