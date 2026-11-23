import unittest
from .validate_overlap_views import views

class OverlapViewTests(unittest.TestCase):
    def test_views_use_disjoint_actual_observations(self):
        track={'direction':'eastbound','points':[[i/2,i*5,10] for i in range(41)]}
        original={tuple(p) for p in track['points']}
        for width in (40,50,60):
            a,b=views(track,width)
            self.assertTrue({tuple(p) for p in a['points']}<=original)
            self.assertTrue({tuple(p) for p in b['points']}<=original)
            self.assertFalse({p[0] for p in a['points']}&{p[0] for p in b['points']})

    def test_discontinuous_source_is_not_ground_truth(self):
        tr={'direction':'eastbound','points':[[i*2,i*20,10] for i in range(41)]}
        self.assertIsNone(views(tr,60))
