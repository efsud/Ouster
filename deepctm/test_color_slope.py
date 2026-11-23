import copy,unittest
from .color_slope import bridge,associate,color_band,generate
class ColorSlopeTests(unittest.TestCase):
 def test_exact_slope(self):
  a=dict(t=0,x=0,v=10.2);b=dict(t=10,x=102,v=10.8)
  p=bridge(a,b);self.assertEqual(p['residual_m'],0)
  self.assertTrue(all(abs(x-10.2*t)<1e-8 for t,x,v in p['points']))
 def test_small_end_correction(self):
  p=bridge(dict(t=0,x=0,v=10),dict(t=10,x=101,v=10))
  self.assertIsNotNone(p);self.assertEqual(p['points'][-1][1],101)
  self.assertTrue(all(x==10*t for t,x,v in p['points'] if t<=8))
 def test_reject_color_time_and_jump(self):
  a=dict(t=0,x=0,v=10)
  for b in (dict(t=10,x=100,v=11),dict(t=0,x=0,v=10),dict(t=10,x=120,v=10),dict(t=10,x=-100,v=-10)):
   self.assertIsNone(bridge(a,b))
 def test_chronological_one_to_one(self):
  left=[dict(t=2,x=20,v=10),dict(t=0,x=0,v=10)]
  right=[dict(t=10,x=100,v=10)]
  matches=associate(left,right);self.assertEqual([m['left'] for m in matches],[1])
 def test_ambiguous_tie(self):
  self.assertEqual(associate([dict(t=0,x=0,v=10)],[dict(t=10,x=100,v=10),dict(t=11,x=110,v=10)]),[])
 def test_nearest_same_color(self):
  m=associate([dict(t=0,x=0,v=10)],[dict(t=10,x=100.8,v=10),dict(t=10,x=100,v=10),dict(t=10,x=100,v=12)])
  self.assertEqual(m[0]['right'],1)
 def test_westbound_and_stationary(self):
  self.assertIsNotNone(bridge(dict(t=0,x=100,v=-10),dict(t=10,x=0,v=-10)))
  self.assertIsNone(bridge(dict(t=0,x=0,v=0),dict(t=10,x=1,v=0)))
 def test_inputs_unchanged(self):
  points=[[i*.5,i*5,10] for i in range(31) if not 5<i*.5<10]
  s=dict(start=0,end=15,generated_at=1,sites=[dict(id='a',tracks=[dict(points=points,direction='eastbound',class_type='2',source_key=['s','id',1])])])
  before=copy.deepcopy(s);r=generate(s);self.assertEqual(s,before);self.assertEqual(len(r['within_intersection']),1)
if __name__=='__main__':unittest.main()
