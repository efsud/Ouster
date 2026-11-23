import unittest
from .matching_assignment import associate
class PartialAssignmentTests(unittest.TestCase):
    params={'vmax':25.,'amin':-6.,'amax':4.}
    def ep(self,t,x,v=10):return dict(t=t,x=x,v=v,class_type='2')
    def test_unique_supported_pair(self):
        self.assertEqual(len(associate([self.ep(0,0)],[self.ep(10,100)],self.params)),1)
    def test_ambiguous_duplicates_remain_unresolved(self):
        a=self.ep(0,0);b=self.ep(10,100)
        self.assertEqual(associate([a,a],[b,b],self.params),[])
    def test_physically_impossible_remains_unmatched(self):
        self.assertEqual(associate([self.ep(0,0)],[self.ep(1,100)],self.params),[])
    def test_missing_arrivals_do_not_force_connections(self):
        a=self.ep(0,0);b=self.ep(10,100)
        result=associate([a,self.ep(1000,0)],[b],self.params)
        self.assertEqual([(p['left'],p['right']) for p in result],[(0,0)])
