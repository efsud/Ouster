import unittest,copy
import numpy as np
from datetime import datetime,timedelta
from .local_lateral_recovery import reconstruct
from .test_local_tracklet_matching import track
from .reconstruction_layers import prediction
REPORT={'selected_method':'kinematic_0.01','calibration':{'parameters':{'vmax':30,'amin':-4,'amax':3}}}
class LocalLateralRecoveryTests(unittest.TestCase):
 def pair(self):
  a,b=track('same',0,3),track('same',8,11,3.5)
  a['lateral_end_context']=[[p[0],0] for p in a['points'][-5:]]
  b['lateral_start_context']=[[p[0],3.5] for p in b['points'][:5]]
  return a,b
 def solve(self,a,b):return reconstruct({'id':'site','tracks':[a,b]},lambda x,y:prediction(x,y,REPORT,exact_join=True))
 def test_supported_short_same_id_gap(self):
  a,b=self.pair();original=copy.deepcopy([a,b]);r=self.solve(a,b)
  self.assertEqual(len(r),1);self.assertEqual(r[0]['identity'],'same_sensor_session_id');self.assertEqual([a,b],original)
 def test_other_id_session_clock_and_direction_rejected(self):
  for field,value in [('source_key',['session','different','2']),('source_key',['other','same','2']),('sensor_start','2026-01-02'),('direction','westbound')]:
   a,b=self.pair();b[field]=value;self.assertEqual(self.solve(a,b),[])
 def test_wide_lateral_or_missing_context_rejected(self):
  a,b=self.pair();b['lateral_start_m']=9;self.assertEqual(self.solve(a,b),[])
  a,b=self.pair();del b['lateral_start_context'];self.assertEqual(self.solve(a,b),[])
 def test_ordinary_gaps_not_duplicated(self):
  a,b=self.pair();b['lateral_start_m']=1;self.assertEqual(self.solve(a,b),[])
 def test_long_gap_not_relaxed(self):
  a,b=self.pair();b['points']=[[p[0]+10,p[1]+100,p[2]] for p in b['points']];self.assertEqual(self.solve(a,b),[])
 def test_integration_preserves_existing_paths_and_site_gate(self):
  from .reconstruction_layers import generate
  a,b=self.pair();c,d=track('ordinary',20,23),track('ordinary',28,31)
  site={'id':'site','tracks':[a,b,c,d],'local_gap_candidates':[]}
  snap={'sites':[site],'start':0,'end':40,'generated_at':1}
  report=dict(REPORT,state='evaluated_ablation',test={},uncertainty={})
  old=generate(snap,report,same_class_recovery=True)
  withheld=generate(snap,report,same_class_recovery=True,local_lateral=True,local_lateral_sites=['other'])
  new=generate(snap,report,same_class_recovery=True,local_lateral=True,local_lateral_sites=['site'])
  self.assertEqual(old['within_intersection'],withheld['within_intersection'])
  self.assertEqual(len(new['within_intersection']),len(old['within_intersection'])+1)
  for path in old['within_intersection']:self.assertIn(path,new['within_intersection'])
  self.assertEqual(old['between_intersections'],new['between_intersections'])
if __name__=='__main__':unittest.main()
