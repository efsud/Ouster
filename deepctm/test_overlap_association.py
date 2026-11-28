import unittest
from .overlap_association import evidence,associate

class OverlapAssociationTests(unittest.TestCase):
    def track(self,offset=0,start=0,end=10):
        return {'direction':'eastbound','points':[[t,t*10+offset,10] for t in range(start,end+1)]}
    def test_shared_observations_can_support_a_hypothesis(self):
        a=self.track(end=8);b=self.track(start=4)
        r=associate([a],[b]);self.assertEqual(len(r),1)
        self.assertEqual(r[0]['evidence']['identity'],'unverified_projected_coverage_overlap')
    def test_parallel_indistinguishable_tracks_remain_unmatched(self):
        a=self.track();self.assertEqual(associate([a,a],[a,a]),[])
    def test_no_extrapolation_or_automatic_clock_fit(self):
        self.assertIsNone(evidence(self.track(end=4),self.track(start=5)))
        self.assertIsNone(evidence(self.track(),self.track(offset=10)))
    def test_unobserved_hole_does_not_count_as_overlap(self):
        a=self.track();b=self.track();b['points']=[b['points'][0],b['points'][-1]]
        self.assertIsNone(evidence(a,b))
