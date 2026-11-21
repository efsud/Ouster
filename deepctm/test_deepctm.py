import json
from pathlib import Path
import tempfile
import unittest
from datetime import datetime,timezone
import numpy as np
import torch
from .model import DeepCTM,ctm_step,mass_error
from .features import extract_site,split_sequences,clip_segment
from .experiment import train_direction

CONFIG=json.loads(Path('config/deepctm.json').read_text())

class PhysicsTests(unittest.TestCase):
    def test_conservation_and_jam_bounds_over_15_minutes(self):
        lengths=torch.tensor([.1,.4,.1],dtype=torch.float64)
        before=torch.tensor([[0.,120.,280.],[300.,300.,300.]],dtype=torch.float64)
        after,flow,_=ctm_step(before,torch.tensor([4000.,0.],dtype=torch.float64),lengths)
        self.assertLess(float(mass_error(before,after,flow,lengths,.25).max()),1e-9)
        self.assertTrue(bool((after>=-1e-9).all() and (after<=300+1e-9).all()))
    def test_backward_and_output_shape(self):
        torch.set_num_threads(1);torch.manual_seed(2)
        model=DeepCTM(CONFIG);x=torch.rand(2,2,3,3)*torch.tensor([300.,20.,30.]);mask=torch.tensor([[[True,False,True]]*2]*2)
        out=model(x,mask,4);self.assertEqual(out['prediction'].shape,(2,4,3,3))
        target=torch.ones_like(out['prediction']);valid=mask[:,:1].expand(-1,4,-1)
        loss,_=model.loss(out,target,valid);loss.backward()
        self.assertTrue(all(torch.isfinite(p.grad).all() for p in model.parameters() if p.grad is not None))
        for parameter in [model.forward_message.weight,model.backward_message.weight,model.pec[0].weight,model.gate.weight]:
            self.assertGreater(float(parameter.grad.abs().sum()),0)
    def test_virtual_targets_do_not_change_supervised_loss(self):
        model=DeepCTM(CONFIG);pred=torch.ones(1,4,3,3);target=pred.clone();mask=torch.tensor([[[True,False,True]]*4])
        out={'prediction':pred,'physics':pred,'pec':torch.tensor(0.)}
        first=model.loss(out,target,mask)[1][0];target[:,:,1]=100000
        self.assertEqual(float(first),float(model.loss(out,target,mask)[1][0]))
    def test_future_not_an_input_and_deterministic_evaluation(self):
        torch.manual_seed(4);model=DeepCTM(CONFIG).eval();x=torch.ones(1,2,3,3);mask=torch.tensor([[[True,False,True]]*2])
        with torch.no_grad():a=model(x,mask,4)['prediction'];b=model(x,mask,4)['prediction']
        self.assertTrue(torch.equal(a,b))

class FeatureTests(unittest.TestCase):
    def event(self,t,x,session='a'):
        return {'session':session,'received_at':t,'payload':{'timestamp':datetime.fromtimestamp(t,timezone.utc).isoformat(),'frame':{'objects':[{'id':'1','classType':'2','centerX':x,'centerY':0}]}}}
    def test_edie_units_direction_and_no_data_mask(self):
        config={**CONFIG,'interval_s':10,'minimum_coverage':.8,'road_bearing_east_deg':0}
        rows=[self.event(t,-40+8*t) for t in range(10)]
        values,mask,evidence=extract_site(rows,0,20,0,config)
        self.assertAlmostEqual(values[0,0,0],259.2);self.assertAlmostEqual(values[0,0,1],9);self.assertAlmostEqual(values[0,0,2],28.8)
        self.assertTrue(mask[0,0]);self.assertFalse(mask[0,1]);self.assertFalse(mask[1].any())
    def test_session_and_clock_gaps_not_crossed(self):
        config={**CONFIG,'interval_s':10,'minimum_coverage':0,'road_bearing_east_deg':0}
        x,mask,_=extract_site([self.event(0,-1),self.event(1,1,'b'),self.event(8,3,'b')],0,10,0,config)
        self.assertEqual(float(x.sum()),0);self.assertFalse(mask.any())
    def test_clip_boundary_and_cross_street(self):
        self.assertEqual(clip_segment((-100,0),(100,0),100,12),(.25,.75))
        self.assertIsNone(clip_segment((0,20),(10,20),100,12))
    def test_split_no_leakage_or_gap_interpolation(self):
        x=np.zeros((100,3,3),dtype=np.float32);mask=np.ones((100,3),dtype=bool);mask[:,1]=False;mask[30]=False
        splits=split_sequences(x,mask,4,4)
        self.assertTrue(all(i+4<=60 for i in splits['train']))
        self.assertTrue(all(i-4>=60 and i+4<=80 for i in splits['validation']))
        self.assertTrue(all(i-4>=80 for i in splits['test']))
        self.assertTrue(all(not i-4<=30<i+4 for i in splits['train']))
    def test_short_capture_refuses_training(self):
        x=np.zeros((10,3,3),dtype=np.float32);mask=np.ones((10,3),dtype=bool)
        with tempfile.TemporaryDirectory() as tmp:
            result=train_direction(x,mask,CONFIG,1,tmp,'eastbound',0)
        self.assertEqual(result['state'],'insufficient_data')

if __name__=='__main__':unittest.main()
