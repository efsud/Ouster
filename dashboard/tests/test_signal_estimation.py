import unittest
from dashboard.signal_estimation import Learner,point,classify

class EstimatorTest(unittest.TestCase):
    def test_projection_and_direction(self):
        self.assertEqual(point({'centerX':10,'centerY':2},{'preview_rotation_deg':0,'preview_mirror_y':True}),(10,-2))
        self.assertEqual(classify((10,1)),'E')
        self.assertEqual(classify((-10,1)),'W')
        self.assertIsNone(classify((10,10)))

    def test_stopped_release_requires_crossing_not_turn(self):
        l=Learner({'id':'S','preview_rotation_deg':0})
        def step(t,x,y=0):
            phase={'session':'a','initialized':True,'phases':{'2':{'status':'RED' if t<4 else 'GREEN','received_at':t}}}
            l.ingest(t,'a',str(t),[{'id':'v','classType':1,'centerX':x,'centerY':y}],phase)
        for t in range(1,5):step(t,-15)
        step(5,-12);step(6,-8)
        self.assertFalse(l.releases)
        step(7,-2);step(8,9)
        self.assertEqual(len(l.releases),1)
        self.assertEqual(l.releases[0]['direction'],'E')
        self.assertIn('2',l.releases[0]['near_onset'])
        step(20,12)
        self.assertFalse(l.releases) # outage discards evidence

    def fixture(self,tied=False):
        l=Learner({'id':'S'});l.session='a';l.last=700
        l.samples=[(i,{'2':'GREEN' if i%100<30 else 'RED','6':('GREEN' if i%100<30 else 'RED') if tied else 'RED'}) for i in range(701)]
        l.cycles=[(i,'2') for i in (100,200,300)]
        l.releases=[{'time':100+i*50,'direction':'E','phases':{'2':'GREEN','6':'GREEN' if tied else 'RED'},'near_onset':['2','6'] if tied else ['2'],'onset_times':{'2':100+(i//3)*100,'6':100+(i//3)*100}} for i in range(9)]
        return l

    def test_support_margin_and_ambiguity(self):
        l=self.fixture();self.assertTrue(l.report(700)['directions']['E']['accepted'])
        self.assertFalse(l.report(700)['directions']['W']['accepted'])
        self.assertFalse(self.fixture(True).report(700)['directions']['E']['accepted'])
        l.releases=l.releases[:3]
        self.assertFalse(l.report(700)['directions']['E']['accepted'])
