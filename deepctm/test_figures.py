import unittest
from datetime import datetime,timezone
from .figures import trajectories

class TrajectoryFiguresTest(unittest.TestCase):
    def row(self,t,x,session='a'):
        return {'received_at':t,'session':session,'payload':{'timestamp':datetime.fromtimestamp(t,timezone.utc).isoformat(),'frame':{'objects':[{'id':'7','classType':'2','centerX':x,'centerY':0}]}}}
    def test_measured_direction_and_speed(self):
        tracks,_=trajectories([self.row(t,t*2) for t in range(5)],0,0)
        self.assertEqual(len(tracks),1);self.assertEqual(tracks[0]['direction'],'eastbound')
        self.assertTrue((tracks[0]['points'][1:,2]==2).all())
    def test_gaps_and_sessions_split_tracks(self):
        rows=[self.row(t,t*2) for t in range(4)]+[self.row(t,t*2) for t in range(10,14)]+[self.row(t,t*2,'b') for t in range(14,18)]
        tracks,_=trajectories(rows,0,0);self.assertEqual(len(tracks),3)
        self.assertTrue(all(t['points'][-1,0]-t['points'][0,0]<=3 for t in tracks))
    def test_stationary_and_outside_roi_not_claimed_through(self):
        self.assertEqual(trajectories([self.row(t,0) for t in range(5)],0,0)[0],[])
        self.assertEqual(trajectories([self.row(t,200+t*2) for t in range(5)],0,0)[0],[])
    def test_westbound(self):
        tracks,_=trajectories([self.row(t,10-t*2) for t in range(5)],0,0)
        self.assertEqual(tracks[0]['direction'],'westbound')
