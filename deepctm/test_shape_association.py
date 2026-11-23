import unittest
from .shape_association import associate
from .object_shape import summarize
class ShapeMatchingTests(unittest.TestCase):
    params={'vmax':30,'amin':-4,'amax':3}
    def ep(self,t,x,size=None):return {'t':t,'x':x,'v':10,'class_type':'2','shape':summarize([size]*5) if size else None}
    def test_missing_dimensions_does_not_break_a_tie(self):
        a=self.ep(0,0);b=self.ep(10,100)
        self.assertEqual(associate([a,a],[b,b],self.params),[])
    def test_distinct_visible_dimensions_can_disambiguate(self):
        a=self.ep(0,0,[2,4]);b=self.ep(0,0,[2.5,7]);c=self.ep(10,100,[2,4]);d=self.ep(10,100,[2.5,7])
        result=associate([a,b],[d,c],self.params,weight=.5)
        self.assertEqual({(m['left'],m['right']) for m in result},{(0,1),(1,0)})
    def test_shape_never_overrides_impossible_motion(self):
        self.assertEqual(associate([self.ep(0,0,[2,4])],[self.ep(1,100,[2,4])],self.params),[])

    def test_absent_shape_cannot_gain_from_penalizing_a_known_competitor(self):
        left=[self.ep(0,0,None),self.ep(0,0,[2.5,7])];right=[self.ep(10,100,[2,4])]
        self.assertEqual(associate(left,right,self.params,weight=.5),[])
