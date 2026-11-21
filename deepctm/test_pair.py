import unittest,json
from pathlib import Path
import numpy as np
import torch
from .model import DeepCTM,ctm_step,mass_error
from .features import extract_site
from .florida_pair import pair_sequences,configuration
from .test_deepctm import FeatureTests,CONFIG

class PairTests(unittest.TestCase):
    def test_fl_geometry_and_masked_splits(self):
        c=configuration();self.assertEqual(c['sites_west_to_east'],['OBC-AG-SA-C257225','OBC-AG-SA-C257206'])
        self.assertAlmostEqual(sum(c['cell_lengths_km'])*1000,c['origin_distance_m']+60)
        m=np.ones((540,8),bool);m[:,1:-1]=False;m[340]=False
        s=pair_sequences(m,12,12)
        self.assertTrue(s['validation']);self.assertTrue(all(i-12>=324 and i+12<=432 for i in s['validation']))
        self.assertTrue(all(i+12<=324 for i in s['train']))
        self.assertTrue(all(i-12>=432 for i in s['test']))
    def test_mirror_changes_direction(self):
        rows=[FeatureTests().event(i,0) for i in range(10)]
        for i,r in enumerate(rows):r['payload']['frame']['objects'][0]['centerY']=-40+8*i
        cfg={**CONFIG,'interval_s':10,'road_bearing_east_deg':0}
        a,ma,_=extract_site(rows,0,10,90,cfg)
        b,mb,_=extract_site(rows,0,10,90,{**cfg,'mirror_y':True})
        self.assertTrue(ma[0,1]);self.assertTrue(mb[0,0]);self.assertAlmostEqual(a[0,1,0],b[0,0,0])
    def test_empty_flow_is_valid_but_speed_is_not_observed(self):
        rows=[FeatureTests().event(i,0) for i in range(10)]
        for row in rows:row['payload']['frame']['objects']=[]
        cfg={**CONFIG,'interval_s':10,'road_bearing_east_deg':0,'empty_bins_valid':True}
        x,m,q=extract_site(rows,0,20,0,cfg)
        self.assertTrue(m[0].all());self.assertFalse(m[1].any());self.assertEqual(x[0,0,0],0)
        self.assertFalse(any(q['speed_observed'][0]))
    def test_masked_features_cannot_influence_prediction_or_loss(self):
        cfg={**CONFIG,'interval_s':10};model=DeepCTM(cfg).eval()
        x=torch.ones(1,3,3,3);mask=torch.tensor([[[True,False,True]]*3]);fm=mask[...,None].expand_as(x).clone();fm[...,2]=False
        with torch.no_grad():
            first=model(x,mask,1,fm);x[...,2]=10000;second=model(x,mask,1,fm)
        self.assertTrue(torch.equal(first['prediction'],second['prediction']))
        target=torch.ones_like(first['prediction']);valid=mask[:,:1];tf=fm[:,:1]
        l=model.loss(first,target,valid,tf)[0];target[...,2]=1e6
        self.assertEqual(float(l),float(model.loss(first,target,valid,tf)[0]))
    def test_signal_red_blocks_flow_and_conserves(self):
        k=torch.tensor([[50.,100.,150.]],dtype=torch.float64);lengths=torch.tensor([.03,.03,.03],dtype=torch.float64)
        gate=torch.tensor([1.,0.,1.,0.],dtype=torch.float64)
        end,flows,_=ctm_step(k,torch.tensor([2000.],dtype=torch.float64),lengths,10/3600,signal_mask=gate)
        self.assertEqual(float(flows[0,1]),0);self.assertEqual(float(flows[0,-1]),0)
        self.assertLess(float(mass_error(k,end,flows,lengths,10/3600).max()),1e-9)
        self.assertTrue(bool((end<=300).all()))

class PairTracerTests(unittest.TestCase):
    def test_both_directions_stay_in_link_and_forecast_window(self):
        from .pair_view import paths
        field=np.zeros((12,8,3));field[...,2]=36
        lengths=[.06]+[.0375]*6+[.06]
        for direction in ['eastbound','westbound']:
            for path in paths(field,lengths,10,direction,285):
                self.assertTrue(all(0<=t<=120 and 30<=x<=255 and v==10 for t,x,v in path['points']))
                self.assertTrue(all(b[0]>a[0] for a,b in zip(path['points'],path['points'][1:])))
                self.assertTrue(all((b[1]-a[1])*(1 if direction=='eastbound' else -1)>=0 for a,b in zip(path['points'],path['points'][1:])))
    def test_stationary_predictions_do_not_create_motion(self):
        from .pair_view import paths
        field=np.zeros((12,8,3));out=paths(field,[.06]+[.0375]*6+[.06],10,'eastbound',285)
        self.assertTrue(all(p[1]==30 for path in out for p in path['points']))
    def test_triangular_fundamental_diagram_and_downstream_supply(self):
        lengths=torch.tensor([.04,.04,.04],dtype=torch.float64)
        for density in [10.,80.,240.]:
            q=min(50*density,18*(300-density),50*18*300/68)
            k=torch.full((1,3),density,dtype=torch.float64)
            end,flow,_=ctm_step(k,torch.tensor([q],dtype=torch.float64),lengths,30/3600,downstream_density=torch.tensor([density],dtype=torch.float64))
            self.assertTrue(torch.allclose(end,k,atol=1e-10));self.assertTrue(torch.allclose(flow,torch.full_like(flow,q),atol=1e-8))
