import json,unittest
from datetime import datetime,timezone
from .florida_rolling import connect,build
class ClassContinuityTests(unittest.TestCase):
    def build_case(self,classes,merge):
        db=connect(':memory:')
        for i,cls in enumerate(classes):
            t=1000+i*.5
            raw={'timestamp':datetime.fromtimestamp(t,timezone.utc).isoformat(),'frame':{'objects':[{'id':'a','classType':cls,'centerX':i,'centerY':0}]}}
            db.execute('insert into frames values(?,?,?,?,?)',('site','session',str(i),t,json.dumps(raw)))
        db.commit();s={'id':'site','name':'site','region':'Florida','reference_location':{'lat':0,'lng':0},'preview_rotation_deg':0}
        result=build(db,[s],1100,merge_vehicle_classes=merge);db.close();return result['sites'][0]['tracks']
    def test_preserves_observations_and_actual_class_counts(self):
        self.assertEqual(self.build_case(['2','4']*10,False),[])
        tracks=self.build_case(['2','4']*10,True)
        self.assertEqual(len(tracks),1);self.assertEqual(len(tracks[0]['points']),20)
        self.assertEqual(tracks[0]['observed_class_counts'],{'2':10,'4':10})
    def test_nonvehicle_transition_still_splits(self):
        tracks=self.build_case(['2']*10+['10']*10+['2']*10,True)
        self.assertGreaterEqual(len(tracks),3)
        self.assertTrue(all(not ('2' in t['observed_class_counts'] and '10' in t['observed_class_counts']) for t in tracks))
