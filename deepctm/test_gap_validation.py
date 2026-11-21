import unittest
from datetime import datetime,timedelta
from .validate_gaps import evaluate_track

class MaskedGapTests(unittest.TestCase):
    def points(self):
        base=datetime(2026,1,1)
        return [(i*.5,-20+i*.5,0,1,base+timedelta(seconds=i*.5)) for i in range(90)]
    def test_thirty_second_mask_is_included(self):
        r=evaluate_track(self.points(),30)
        self.assertTrue(r['accepted']);self.assertEqual(r['duration'],30);self.assertLess(r['mae_m'],1e-8)
    def test_hidden_truth_does_not_enter_estimator(self):
        points=self.points();first=evaluate_track(points,10)
        # Strictly interior to centered 10s mask (17--27s), never boundary context.
        changed=[(t,x+2 if 19<t<24 else x,y,v,stamp) for t,x,y,v,stamp in points]
        second=evaluate_track(changed,10)
        self.assertEqual(first['example']['estimated_m'],second['example']['estimated_m'])
        self.assertGreater(second['mae_m'],first['mae_m'])
    def test_discontinuous_truth_is_not_used(self):
        p=self.points();self.assertIsNone(evaluate_track(p[:20]+p[30:],10))

class BalancedLossTests(unittest.TestCase):
    def test_missing_features_do_not_affect_balanced_loss(self):
        import torch
        from .model import DeepCTM
        from .test_deepctm import CONFIG
        model=DeepCTM({**CONFIG,'balanced_features':True,'data_loss_scales':[100,5,5]})
        target=torch.zeros(1,1,3,3);prediction=torch.ones_like(target)
        result={'prediction':prediction,'physics':prediction,'pec':torch.tensor(0.)}
        mask=torch.ones(1,1,3,dtype=torch.bool);fm=mask[...,None].expand_as(target).clone();fm[...,2]=False
        first=model.loss(result,target,mask,fm)[0]
        target[...,2]=9999
        self.assertEqual(float(first),float(model.loss(result,target,mask,fm)[0]))
