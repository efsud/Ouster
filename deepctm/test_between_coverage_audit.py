import unittest
from .between_coverage_audit import overlap_link
from .residual_color_slope import Reservations

class OverlapAuditTest(unittest.TestCase):
    def fixture(self,offset=0):
        def track(start,end,shift=0):
            return dict(direction='eastbound',class_type='2',source_key=['session',str(start),'2'],points=[[i,10*i+shift,10] for i in range(start,end+1)])
        up=dict(id='up',name='Up',station_m=0,tracks=[track(0,12)])
        down=dict(id='down',name='Down',station_m=200,tracks=[track(6,20,offset)])
        left=[dict(site='up',fragment=0,t=12,x=120,v=10)]
        right=[dict(site='down',fragment=0,t=6,x=60+offset,v=10)]
        return left,right,up,down
    def test_overlap_is_evidence_not_backward_bridge(self):
        r=overlap_link(*self.fixture())
        self.assertEqual(r['median_signed_end_to_start_m'],-60)
        self.assertEqual(r['overlap_hypotheses'],1)
        self.assertNotIn('points',r['hypotheses'][0])
        self.assertEqual(r['hypotheses'][0]['evidence']['median_position_disagreement_m'],0)
    def test_occupied_gap_endpoint_not_reused(self):
        reserved=Reservations([dict(sites=['up','elsewhere'],direction='eastbound',points=[[12,120,10],[20,200,10]])])
        r=overlap_link(*self.fixture(),reservations=reserved)
        self.assertEqual(r['overlap_hypotheses'],0)
    def test_clock_or_position_mismatch_rejected(self):
        r=overlap_link(*self.fixture(30))
        self.assertEqual(r['overlap_hypotheses'],0)
    def test_absent_spatial_overlap_not_invented(self):
        r=overlap_link(*self.fixture(300))
        self.assertEqual(r['overlap_hypotheses'],0)
        self.assertGreater(r['median_signed_end_to_start_m'],0)

if __name__=='__main__':unittest.main()
