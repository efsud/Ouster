"""New local links must reserve endpoints before corridor association."""
import copy
import unittest
from unittest.mock import patch

from .reconstruction_layers import generate


class BoundaryIntegrationTests(unittest.TestCase):
    def test_new_local_bridge_reserves_both_internal_endpoints(self):
        tracks=[dict(source_key=['session','vehicle','2'],class_type='2',
                     direction='eastbound',points=points)
                for points in ([[0,100,1],[1,101,1]],
                               [[11.5,111.5,1],[12.5,112.5,1]])]
        snapshot=dict(start=0,end=20,generated_at=20,sites=[dict(
            id='site',tracks=tracks,local_gap_candidates=[])])
        original=copy.deepcopy(snapshot)
        bridge=dict(site='site',identity_key=['session','vehicle'],
                    identity='same_sensor_session_id_boundary_retry',
                    points=[[1,101,1],[11.5,111.5,1]])
        report=dict(state='evaluated_ablation',selected_method='kinematic_0.01',
                    calibration={'parameters':{'vmax':25,'amin':-6,'amax':4}},
                    test={},uncertainty={})
        def association(source,**kwargs):
            left,right=source['sites'][0]['tracks']
            self.assertEqual(left['internal_chain_endpoints'],['departure'])
            self.assertEqual(right['internal_chain_endpoints'],['arrival'])
            return {'links':[]}
        with patch('deepctm.instantaneous_boundary_layer.apply',return_value={
                'within_intersection':[bridge],
                'instantaneous_boundary_review':{'added':1}}), \
             patch('deepctm.reconstruction_layers.reconstruct',side_effect=association):
            result=generate(snapshot,report,terminal_chains=True,
                            instantaneous_boundary_policy={'enabled':True})
        self.assertEqual(result['within_intersection'],[bridge])
        self.assertEqual(result['between_intersections'],[])
        self.assertEqual(snapshot,original)


if __name__=='__main__':
    unittest.main()
