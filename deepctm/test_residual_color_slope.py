import copy,unittest
from .residual_color_slope import generate,Reservations,remaining_matches

class ResidualColorTests(unittest.TestCase):
 def snapshot(self):
  points=[[i*.5,i*5,10] for i in range(31) if not 5<i*.5<8]
  return dict(start=0,end=15,generated_at=1,sites=[dict(id='a',tracks=[dict(points=points,direction='eastbound',class_type='2',source_key=['s','id','2'])])])
 def test_additive_and_input_immutable(self):
  s=self.snapshot();old=copy.deepcopy(s);baseline=dict(within_intersection=[],between_intersections=[])
  r=generate(s,baseline);self.assertEqual(s,old);self.assertEqual(len(r['within_intersection']),1)
  baseline['within_intersection']=r['within_intersection']
  self.assertEqual(generate(s,baseline)['within_intersection'],[])
 def test_existing_other_layer_reserves_both_roles(self):
  path=dict(sites=['a','b'],direction='eastbound',points=[[0,0,10],[10,100,10]])
  r=Reservations([path]);a=dict(site='a',direction='eastbound',t=0,x=0,v=10);b=dict(site='b',direction='eastbound',t=10,x=100,v=10)
  self.assertTrue(r.occupied(a,True));self.assertTrue(r.occupied(b,False));self.assertFalse(r.occupied(a,False))
  self.assertEqual(remaining_matches([a],[b],r),[])
 def test_intervening_observation_is_not_overwritten(self):
  s=self.snapshot();middle=copy.deepcopy(s['sites'][0]['tracks'][0]);middle['points']=[[6,60,10],[6.5,65,10],[7,70,10]]
  s['sites'][0]['tracks'].append(middle)
  r=generate(s,dict(within_intersection=[],between_intersections=[]));self.assertEqual(r['within_intersection'],[])
 def test_chronological_nearest_unreserved_color(self):
  a=dict(site='a',direction='eastbound',t=0,x=0,v=10)
  right=[dict(site='b',direction='eastbound',t=10,x=100,v=10),dict(site='b',direction='eastbound',t=11,x=110.8,v=10)]
  r=Reservations([dict(sites=['other','b'],direction='eastbound',points=[[-1,0,10],[10,100,10]])])
  m=remaining_matches([a],right,r);self.assertEqual(m[0]['right'],1)
