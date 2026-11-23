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


class SameClassRecoveryTests(unittest.TestCase):
    def test_lateral_experiment_never_silently_widens_default(self):
        a=track('same',0,3);b=track('same',8,11);b['lateral_start_m']=3.5
        self.assertEqual(list(candidates({'tracks':[a,b]},include_same_class=True)),[])
        rows=list(candidates({'tracks':[a,b]},include_same_class=True,allow_lateral_motion=True))
        self.assertEqual(len(rows),1);self.assertTrue(rows[0]['requires_lateral_check'])
    def test_same_class_recovery_is_explicit(self):
        a=track('same',0,3);b=track('same',8,11)
        self.assertEqual(list(candidates({'tracks':[a,b]})),[])
        found=list(candidates({'tracks':[a,b]},include_same_class=True))
        self.assertEqual(len(found),1);self.assertFalse(found[0]['classification_changed'])
    def test_intervening_nonvehicle_track_is_not_skipped(self):
        a=track('same',0,3);b=track('same',10,13);middle=track('same',5,8)
        middle['class_type']='pedestrian';middle['source_key'][2]='pedestrian'
        self.assertEqual(list(candidates({'tracks':[a,middle,b]},include_same_class=True)),[])
    def test_long_gap_still_requires_recording_outage(self):
        a=track('same',0,3);b=track('same',63,66)
        self.assertEqual(list(candidates({'tracks':[a,b]},include_same_class=True)),[])


class MultipleObjectsDuringOutageTests(unittest.TestCase):
    def test_shared_frame_gap_does_not_deduplicate_different_objects(self):
        from .reconstruction_layers import generate
        tracks=[track(id,start,end) for id in ('one','two') for start,end in ((0,3),(8,11))]
        site={'id':'site','name':'site','tracks':tracks,'receipt_gaps':[[3,8]],'local_gap_candidates':[]}
        report={'state':'evaluated_ablation','selected_method':'kinematic_0.01','calibration':{'parameters':{'vmax':30,'amin':-4,'amax':3}},'test':{},'uncertainty':{}}
        result=generate({'sites':[site],'start':0,'end':100,'generated_at':0},report)
        self.assertEqual(len(result['within_intersection']),2)
        self.assertEqual({tuple(p['identity_key']) for p in result['within_intersection']},{('session','one'),('session','two')})
