import unittest
from deepctm.test_local_tracklet_matching import track
from deepctm.same_id_gaps import candidates
from deepctm.reconstruction_layers import prediction

class SameIdTests(unittest.TestCase):
    def pair(self):
        a=track('same',0,3);b=track('same',8,11)
        b['class_type']='6';b['source_key'][2]='6'
        return a,b
    def test_class_change_preserves_identity(self):
        a,b=self.pair();rows=list(candidates({'tracks':[a,b]}))
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['classes'],['2','6'])
    def test_other_id_session_direction_overlap_and_lateral_rejected(self):
        for change in ('id','session','direction','lateral','clock','movement'):
            a,b=self.pair()
            if change=='id':b['source_key'][1]='different'
            elif change=='session':b['source_key'][0]='different'
            elif change=='direction':b['direction']='westbound'
            elif change=='lateral':b['lateral_start_m']=5
            elif change=='clock':b['sensor_start']='2026-01-02'
            else:b['movement']['movement']='WN'
            self.assertEqual(list(candidates({'tracks':[a,b]})),[],change)
    def test_exact_join_position_and_tangent(self):
        report={'selected_method':'kinematic_0.01','calibration':{'parameters':{'vmax':30,'amin':-4,'amax':3}}}
        for sign in (1,-1):
            a=dict(t=0,x=0,v=sign*5);b=dict(t=10,x=sign*70,v=sign*9)
            p=prediction(a,b,report,exact_join=True)
            self.assertIsNotNone(p)
            self.assertAlmostEqual(p[0][1],a['x'],places=5);self.assertAlmostEqual(p[-1][1],b['x'],places=5)
            self.assertAlmostEqual(p[0][2],5,places=5);self.assertAlmostEqual(p[-1][2],9,places=5)

class RecordingInterruptionTests(unittest.TestCase):
    def test_long_same_id_needs_missing_frames(self):
        a=track('same',0,3);b=track('same',63,66)
        site={'tracks':[a,b]}
        self.assertEqual(list(candidates(site)),[])
        site['receipt_gaps']=[[3,63]]
        rows=list(candidates(site));self.assertEqual(len(rows),1)
        self.assertTrue(rows[0]['recording_gap']);self.assertEqual(rows[0]['missing_receipt_fraction'],1)
    def test_reconnect_session_is_not_same_identity(self):
        a=track('same',0,3);b=track('same',63,66);b['source_key'][0]='new-session'
        self.assertEqual(list(candidates({'tracks':[a,b],'receipt_gaps':[[3,63]]})),[])
    def test_short_outage_can_bridge_same_class(self):
        a=track('same',0,3);b=track('same',10,13)
        self.assertEqual(len(list(candidates({'tracks':[a,b],'receipt_gaps':[[3,10]]}))),1)
