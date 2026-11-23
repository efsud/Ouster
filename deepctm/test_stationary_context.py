import unittest
from .stationary_context import attach

def track(identity,start,end,stationary=False,direction='eastbound'):
    return dict(source_key=['session',identity,'2'],points=[[start,0,0],[end,1,0]],stationary_context=stationary,direction=direction)
class StationaryTests(unittest.TestCase):
    def test_only_same_identity_and_nearby(self):
        moving=track('a',0,10);stopped=track('a',15,25,True)
        self.assertEqual(attach([moving,stopped])[-1]['direction_evidence'],'nearby_same_sensor_session_object_moving_fragment')
        self.assertEqual(len(attach([moving,track('b',15,25,True)])),1)
        self.assertEqual(len(attach([moving,track('a',150,160,True)])),1)
    def test_conflicting_directions_not_assigned(self):
        a=track('a',0,10);b=track('a',30,40,direction='westbound');s=track('a',15,25,True)
        self.assertEqual(len(attach([a,b,s])),2)
    def test_stationary_alone_not_assigned(self):
        self.assertEqual(attach([track('a',0,20,True)]),[])
