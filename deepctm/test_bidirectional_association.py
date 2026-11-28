import unittest
import numpy as np
from .bidirectional_association import motion_context,extrapolate,associate
from .shape_association import associate as reference
from .kinematic_gate import path
P={'vmax':30,'amin':-4,'amax':3}
class BidirectionalTests(unittest.TestCase):
 def test_visible_acceleration(self):
  p=[[t,10*t+t*t,10+2*t] for t in np.arange(-3,.1,.5)]
  c=motion_context(p,True);self.assertAlmostEqual(c['acceleration_mps2'],2)
 def test_gap_context_unavailable(self):
  self.assertIsNone(motion_context([[t,t,1] for t in [0,.5,1,3,3.5,4]],True))
 def test_forward_backward_constant(self):
  e=dict(t=0,x=0,v=10);self.assertEqual(extrapolate(e,5,P),(50,10));self.assertEqual(extrapolate(e,-5,P),(-50,10))
 def test_missing_context_matches_reference(self):
  a=[dict(t=0,x=0,v=10,class_type='2')];b=[dict(t=10,x=100,v=10,class_type='2')]
  r=reference(a,b,P,weight=.5,path_gate=path);q=associate(a,b,P,blend=.5)
  self.assertEqual([(m['left'],m['right']) for m in r],[(m['left'],m['right']) for m in q])
 def test_audit_distinguishes_time_and_direction(self):
  d={};associate([dict(t=5,x=0,v=10)],[dict(t=0,x=10,v=10),dict(t=10,x=-10,v=-10)],P,diagnostics=d)
  self.assertEqual(d['outside_time_window'],1);self.assertEqual(d['direction_or_low_endpoint_speed'],1)
 def test_physical_gate_survives_motion_score(self):
  d={};r=associate([dict(t=0,x=0,v=10)],[dict(t=2,x=300,v=10)],P,blend=.5,diagnostics=d)
  self.assertEqual(r,[])
 def test_zero_blend_reproduces_published_assignments(self):
  rng=np.random.default_rng(32)
  for _ in range(12):
   left=[dict(t=float(i*3),x=0.,v=float(rng.uniform(7,13)),class_type='2') for i in range(8)]
   right=[dict(t=a['t']+100/a['v'],x=100.,v=a['v'],class_type='2') for a in left]
   r=reference(left,right,P,weight=.5,path_gate=path);q=associate(left,right,P,blend=0)
   self.assertEqual([(m['left'],m['right']) for m in r],[(m['left'],m['right']) for m in q])
 def test_production_enricher_uses_visible_fragment(self):
  from .spatial_bridges import reconstruct
  from copy import deepcopy
  sites=[]
  for sid,offset in [('a',0),('b',200)]:
   tracks=[dict(points=[[t+i*5,offset+t*10,10] for t in np.arange(0,3,.5)],direction='eastbound',class_type='2') for i in range(10)]
   sites.append(dict(id=sid,name=sid,tracks=tracks))
  snap=dict(sites=sites);original=deepcopy(snap);seen=[]
  def enrich(ep,tr,side):
   seen.append(side);return dict(ep,motion_context=motion_context(tr['points'],side))
  def match(a,b):
   self.assertTrue(all('motion_context' in e and 'site' in e for e in a+b));return []
  reconstruct(snap,matcher=match,endpoint_enricher=enrich)
  self.assertTrue(seen);self.assertEqual(snap,original)
if __name__=='__main__':unittest.main()
