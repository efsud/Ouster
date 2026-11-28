import unittest
import numpy as np
from .trajectory_reconstruction import baseline,newell,refine,integrate_matrix

class ReconstructionTests(unittest.TestCase):
    def setUp(self):self.a=dict(t=0.,x=0.,v=10.);self.b=dict(t=10.,x=100.,v=10.)
    def test_integrator_obeys_both_kinematic_equations(self):
        t=np.linspace(0,10,21);A,D=integrate_matrix(t);v=2+3*t;x=A@v;a=D@v;dt=np.diff(t)
        np.testing.assert_allclose(np.diff(x),v[:-1]*dt+.5*a*dt**2)
        np.testing.assert_allclose(np.diff(v),a*dt)
    def test_constant_motion_optimizer(self):
        r=refine(self.a,self.b,baseline(self.a,self.b))
        self.assertEqual(r['state'],'candidate');np.testing.assert_allclose(r['points'][:,1],10*r['points'][:,0],atol=.01)
        self.assertIn('ctm_envelope_unavailable',r['unavailable_constraints'])
    def test_infeasible_endpoint_cannot_be_published(self):
        b=dict(t=2.,x=100.,v=10.)
        r=refine(self.a,b,baseline(self.a,b),vmax=20)
        self.assertEqual(r['state'],'infeasible')
    def test_missing_leader_never_masquerades_as_newell(self):
        r=newell(self.a,self.b,[],1.,5.,15.)
        self.assertEqual(r['state'],'unavailable')
    def test_newell_translation(self):
        t=np.arange(-2,11,.5);leader=np.column_stack([t,10*(t+1)+5])
        r=newell(self.a,self.b,leader,1.,5.,10.,True)
        np.testing.assert_allclose(r['points'][:,1],10*r['points'][:,0])
    def test_no_leader_extrapolation(self):
        r=newell(self.a,self.b,[[0,15],[1,25]],1.,5.,10.,True)
        self.assertEqual(r['reason'],'leader_coverage_missing')
    def test_verified_position_ceiling_enforced(self):
        b=dict(t=10.,x=20.,v=4.);a=dict(t=0.,x=0.,v=0.)
        cap=np.column_stack([np.arange(0,5.1,.5),np.full(11,2.)])
        r=refine(a,b,baseline(a,b),red_position_ceiling=cap)
        self.assertEqual(r['state'],'candidate');self.assertTrue(np.all(r['points'][r['points'][:,0]<=5,1]<=2.00001))

class StudySplitTests(unittest.TestCase):
    def test_site_and_time_must_both_match(self):
        from .reconstruction_study import partition_track
        plan={'boundary_embargo_seconds':5,'spatial_partitions':{'train':['a'],'validation':['b'],'test':['c']},'time_fractions':{'train':[0,.6],'validation':[.6,.8],'test':[.8,1]}}
        tr={'class_type':'2','points':[[10+i,0,0] for i in range(12)]}
        self.assertEqual(partition_track('a',tr,{'start':0,'end':100},plan),'train')
        self.assertIsNone(partition_track('c',tr,{'start':0,'end':100},plan))
        tr['points']=[[50+i,0,0] for i in range(12)]
        self.assertIsNone(partition_track('a',tr,{'start':0,'end':100},plan))
    def test_hidden_truth_does_not_change_boundary_inputs(self):
        from .reconstruction_study import masked_case
        tr={'direction':'eastbound','points':[[i*.5,i*2.,4.] for i in range(81)]}
        a,b,truth=masked_case(tr,10)
        for p in tr['points']:
            if a['t']<p[0]<b['t']:p[1]+=7
        aa,bb,other=masked_case(tr,10)
        self.assertEqual(a,aa);self.assertEqual(b,bb);self.assertFalse(np.array_equal(truth,other))

class QueuePriorTests(unittest.TestCase):
    def test_red_holds_internal_outflow(self):
        from .movement_queue import simulate
        r=simulate([.05,.05],[20,20],1,15,5,.3,[.2]*20,[.6]*20,[0]*20,True)
        self.assertEqual(r['state'],'available');self.assertTrue(np.all(r['flow'][:,-1]==0));self.assertLess(r['max_mass_error_vehicles'],1e-10)
    def test_unknown_phase_is_not_permission(self):
        from .movement_queue import simulate
        r=simulate([.05],[20],1,15,5,.3,[.2],[.6],[1],False)
        self.assertEqual(r['state'],'unavailable')
    def test_side_flows_in_conservation(self):
        from .movement_queue import simulate
        r=simulate([.05,.1],[10,15],2,20,5,.3,[.1]*3,[.2]*3,side_arrivals=[[.2,.1]]*3,side_departures=[[.1,.2]]*3)
        self.assertLess(r['max_mass_error_vehicles'],1e-10)
        self.assertTrue(np.all(r['density']>=0));self.assertTrue(np.all(r['density']<=.3))

class CollectionTests(unittest.TestCase):
    def test_readiness_requires_every_partition(self):
        from .collect_reconstruction_study import readiness
        plan={'boundary_embargo_seconds':0,'spatial_partitions':{'train':['a'],'validation':['b'],'test':['c']},'time_fractions':{'train':[0,.6],'validation':[.6,.8],'test':[.8,1]},'gap_seconds':[5,10,20,30]}
        r=readiness({'sites':[],'start':0,'end':3600},plan)
        self.assertFalse(r['ready']);self.assertTrue(any('test' in v for v in r['reasons']))
    def test_overlay_requires_evaluated_report(self):
        from .reconstruction_layers import generate
        with self.assertRaises(ValueError):generate({'sites':[]},{'state':'insufficient_training_data'})
    def test_overlay_prediction_preserves_westbound_direction(self):
        from .reconstruction_layers import prediction
        r={'selected_method':'kinematic_0.01','calibration':{'parameters':{'vmax':30,'amin':-4,'amax':3}}}
        p=prediction(dict(t=0,x=100,v=-10),dict(t=10,x=0,v=-10),r)
        self.assertIsNotNone(p);self.assertTrue(all(b[1]<=a[1]+1e-6 for a,b in zip(p,p[1:])));self.assertTrue(all(v>=0 for t,x,v in p))

class FrozenEvaluationTests(unittest.TestCase):
    def test_overlapping_later_period_rejected(self):
        import json,tempfile
        from pathlib import Path
        from .evaluate_reconstruction_later import run
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'snapshot.json').write_text(json.dumps({'start':110,'end':200}))
            (p/'study.json').write_text(json.dumps({'state':'evaluated_ablation','source_window':[0,100]}))
            with self.assertRaises(ValueError):run(p/'snapshot.json',p/'study.json',p/'report.json')

class LocalAdmissionTests(unittest.TestCase):
    def test_clock_and_lateral_checks_independent_of_old_curve(self):
        from datetime import datetime,timedelta
        from deepctm.local_gaps import gap_evidence
        zero=datetime(2026,1,1)
        before=[(t,0.,0.,0.,zero+timedelta(seconds=t)) for t in (0,.5,1,1.5,2)]
        after=[(t,20.+5*(t-12),0.,5.,zero+timedelta(seconds=t)) for t in (12,12.5,13,13.5,14)]
        self.assertIsNotNone(gap_evidence(before,after))
        self.assertIsNone(gap_evidence(before,[(t,x,y+4,v,stamp) for t,x,y,v,stamp in after]))
        self.assertIsNone(gap_evidence(before,[(t,x,y,v,stamp+timedelta(seconds=60)) for t,x,y,v,stamp in after]))

    def test_internal_render_hole_gets_local_estimate(self):
        from deepctm.reconstruction_layers import generate
        times=[0,.5,1,1.5,2,4,4.5,5,5.5,6]
        tr=dict(source_key=['s','id','2'],class_type='2',direction='eastbound',points=[[t,10*t,10] for t in times])
        site=dict(id='a',name='a',tracks=[tr],local_gap_candidates=[])
        report=dict(state='evaluated_ablation',selected_method='kinematic_0.01',calibration={'parameters':{'vmax':30,'amin':-4,'amax':3}},test={},uncertainty={})
        result=generate(dict(sites=[site],generated_at=0,start=0,end=100),report)
        self.assertEqual(len(result['within_intersection']),1)
        self.assertEqual(result['within_intersection'][0]['gap_s'],2)
        self.assertEqual(result['between_intersections'],[])
