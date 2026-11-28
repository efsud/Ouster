import unittest
from .virtual_paths import tracers
from .features import split_sequences
from .figures import trajectories
from .test_figures import TrajectoryFiguresTest
import numpy as np

class VirtualPathTest(unittest.TestCase):
    def test_tracers_stop_at_missing_prediction_and_stay_in_link(self):
        fields=[{'bin':0,'speed_kmh':[36,36,36]},{'bin':2,'speed_kmh':[36,36,36]}]
        for direction in ['eastbound','westbound']:
            paths=tracers(fields,1000,[0,500],[.1,.4,.1],direction)
            for path in paths:
                points=path['points'];self.assertTrue(all(50<=p[1]<=450 for p in points))
                times=[p[0] for p in points];self.assertTrue(max(times)<1060 or min(times)>=1120)
                differences=np.diff([p[1] for p in points]);self.assertTrue((differences>0).all() if direction=='eastbound' else (differences<0).all())
    def test_chronological_targets_and_context_do_not_cross_splits(self):
        x=np.zeros((60,3,3),np.float32);mask=np.ones((60,3),bool);mask[:,1]=False
        splits=split_sequences(x,mask,4,1)
        for name,lo,hi in [('train',0,36),('validation',36,48),('test',48,60)]:
            self.assertTrue(all(i-4>=lo and i<hi for i in splits[name]))
    def test_object_type_retained_and_class_change_splits_identity(self):
        rows=[TrajectoryFiguresTest().row(t,t*2) for t in range(8)]
        for row in rows[4:]:row['payload']['frame']['objects'][0]['classType']='10'
        tracks,_=trajectories(rows,0,0,all_classes=True)
        self.assertEqual({t['class_type'] for t in tracks},{'2','10'})
        default,_=trajectories(rows,0,0)
        self.assertEqual({t['class_type'] for t in default},{'2'})
