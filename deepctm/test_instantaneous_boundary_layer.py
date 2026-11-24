import copy
from datetime import datetime, timedelta
import unittest
from unittest.mock import patch

import numpy as np

from .instantaneous_boundary_layer import apply, _in_scope, _qualified


class BoundaryLayerTests(unittest.TestCase):
    def fixture(self,duration=10.5,site='OBC-AG-SA-C257227'):
        stamp=datetime(2026,11,24,12)
        before=dict(source_key=['s','target','2'],class_type='2',direction='eastbound',
            points=[[float(t),0.,0.] for t in np.arange(-4,.01,.5)],
            sensor_end=stamp.isoformat(),lateral_end_m=0.,movement={'state':'unknown'})
        after=dict(source_key=['s','target','2'],class_type='2',direction='eastbound',
            points=[[float(t),float((t-duration)**2),float(2*(t-duration))]
                    for t in np.arange(duration,duration+4.01,.5)],
            sensor_start=(stamp+timedelta(seconds=duration)).isoformat(),lateral_start_m=0.,movement={'state':'unknown'})
        snapshot=dict(sites=[dict(id=site,tracks=[before,after])])
        layers=dict(within_intersection=[],between_intersections=[{'untouched':True}])
        report=dict(selected_method='kinematic_0.01',calibration=dict(parameters=dict(vmax=24.5174,amin=-6.,amax=4.)))
        policy=dict(enabled=True,enabled_sites=['OBC-AG-SA-C257227'],
            enabled_site_duration_bands={'OBC-AG-SA-C257227':[[10.,20.]]},
            runtime_site_scopes={'OBC-AG-SA-C257227':[dict(minimum_exclusive_s=10.,maximum_inclusive_s=10.7)]},
            configuration=dict(max_speed_adjustment_mps=4.,max_fit_rmse_m=.2,max_fit_error_m=.6),
            evidence='test-report.json')
        return snapshot,layers,report,policy

    def test_exact_site_band_and_cap_required(self):
        _,_,_,policy=self.fixture()
        self.assertTrue(_in_scope('OBC-AG-SA-C257227',10.5,policy))
        self.assertFalse(_in_scope('OBC-AG-SA-C257227',10.,policy))
        self.assertFalse(_in_scope('OBC-AG-SA-C257227',10.71,policy))
        self.assertFalse(_in_scope('OBC-AG-SA-C257227',18.,policy))
        self.assertFalse(_in_scope('OBC-AG-SA-C257225',10.5,policy))
        narrowed=copy.deepcopy(policy);narrowed['enabled_site_duration_bands']={}
        self.assertFalse(_in_scope('OBC-AG-SA-C257227',10.5,narrowed))

    def test_appends_only_estimated_gap_and_preserves_originals(self):
        snapshot,layers,report,policy=self.fixture();original=copy.deepcopy((snapshot,layers))
        with patch('deepctm.instantaneous_boundary_layer._qualified',return_value=(True,None)):
            result=apply(snapshot,layers,report,policy)
        self.assertEqual(result['instantaneous_boundary_review']['added'],1)
        path=result['within_intersection'][0]
        self.assertTrue(path['estimated'])
        self.assertIn('estimated_endpoint_speed_mps',path)
        self.assertIn('observed_endpoint_speed_mps',path)
        self.assertEqual(path['identity_key'],['s','target'])
        self.assertEqual(result['between_intersections'],layers['between_intersections'])
        self.assertEqual((snapshot,layers),original)
        np.testing.assert_allclose(np.asarray(path['points'])[:,1:],0.,atol=1e-6)

    def test_existing_estimated_paths_are_not_replaced_or_duplicated(self):
        snapshot,layers,report,policy=self.fixture()
        layers['within_intersection']=[dict(site='OBC-AG-SA-C257227',identity_key=['s','target'],
                                           points=[[0.,0.,0.],[10.5,0.,0.]],method='old')]
        original=copy.deepcopy(layers)
        with patch('deepctm.instantaneous_boundary_layer._qualified',return_value=(True,None)):
            result=apply(snapshot,layers,report,policy)
        self.assertEqual(result['within_intersection'],original['within_intersection'])
        self.assertEqual(result['instantaneous_boundary_review']['attempted'],0)

    def test_clock_lateral_session_class_and_duration_gates_retained(self):
        for change in ('clock','lateral','session','class','duration'):
            snapshot,layers,report,policy=self.fixture(duration=11 if change=='duration' else 10.5)
            before,after=snapshot['sites'][0]['tracks']
            if change=='clock':after['sensor_start']='2026-11-24T12:00:01'
            if change=='lateral':after['lateral_start_m']=5.
            if change=='session':after['source_key'][0]='other'
            if change=='class':after['class_type']='3';after['source_key'][2]='3'
            with patch('deepctm.instantaneous_boundary_layer._qualified',return_value=(True,None)):
                result=apply(snapshot,layers,report,policy)
            self.assertEqual(result['instantaneous_boundary_review']['added'],0,change)

    def test_unqualified_runtime_and_observed_inside_gap_keep_baseline(self):
        snapshot,layers,report,policy=self.fixture()
        result=apply(snapshot,layers,report,{'enabled':False})
        self.assertEqual(result['instantaneous_boundary_review']['state'],'disabled')
        self.assertFalse(_qualified({},report)[0])
        with patch('deepctm.instantaneous_boundary_layer._qualified',return_value=(True,None)):
            result=apply(snapshot,layers,report,policy,max_seconds=0)
        self.assertEqual(result['instantaneous_boundary_review']['added'],0)
        self.assertTrue(result['instantaneous_boundary_review']['budget_exhausted'])
        snapshot['sites'][0]['tracks'].append(dict(snapshot['sites'][0]['tracks'][0],points=[[5.,0.,0.],[5.5,0.,0.]]))
        with patch('deepctm.instantaneous_boundary_layer._qualified',return_value=(True,None)):
            result=apply(snapshot,layers,report,policy)
        self.assertEqual(result['instantaneous_boundary_review']['added'],0)


if __name__=='__main__':unittest.main()
