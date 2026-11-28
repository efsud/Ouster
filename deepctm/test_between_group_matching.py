import unittest
from unittest.mock import patch
from .between_group_matching import timing_prior, associate, annotate_endpoints

PARAMS={'vmax':30.,'amin':-4.,'amax':3.}


def ep(t, x, group, ident):
    return dict(t=t,x=x,v=10.,class_type='2',trajectory_group=group,
                local_identity=('site','session',str(ident)))


class GroupMatchingTests(unittest.TestCase):
    def test_group_correspondence_not_group_id_equality(self):
        left=[ep(i*2,0,'departures',i) for i in range(4)]
        right=[ep(i*2+10,100,'arrivals',i) for i in range(4)]
        matches=[dict(left=i,right=i) for i in range(4)]
        p=timing_prior(left[0],right[0],left,right,matches)
        self.assertEqual(p['anchor_count'],3)
        self.assertEqual(p['timing_residual_s'],0)

    def test_candidate_does_not_supply_own_anchor(self):
        left=[ep(i*2,0,'a',i) for i in range(3)]
        right=[ep(i*2+10,100,'b',i) for i in range(3)]
        self.assertIsNone(timing_prior(left[0],right[0],left,right,[dict(left=i,right=i) for i in range(3)]))

    def test_exclude_every_fragment_of_candidate_identity(self):
        left=[ep(i*2,0,'a',j) for i,j in enumerate([0,0,1,2])]
        right=[ep(i*2+10,100,'b',j) for i,j in enumerate([0,0,1,2])]
        self.assertIsNone(timing_prior(left[0],right[0],left,right,[dict(left=i,right=i) for i in range(4)]))

    def test_repeated_fragment_ids_do_not_count_as_multiple_vehicles(self):
        left=[ep(i*2,0,'a',1) for i in range(5)]
        right=[ep(i*2+10,100,'b',i) for i in range(5)]
        self.assertIsNone(timing_prior(left[0],right[0],left,right,[dict(left=i,right=i) for i in range(5)]))

    def test_no_groups_reproduces_baseline(self):
        from .bidirectional_association import associate as baseline
        left=[dict(t=0,x=0,v=10,class_type='2')]
        right=[dict(t=10,x=100,v=10,class_type='2')]
        got=associate(left,right,PARAMS)
        expected=baseline(left,right,PARAMS,blend=.5)
        self.assertEqual([(m['left'],m['right']) for m in got],[(m['left'],m['right']) for m in expected])
        self.assertFalse(any(m['group_assistance'] for m in got))

    def test_keep_one_to_one_and_never_remove_baseline(self):
        left=[ep(i*3,0,'a',i) for i in range(6)]
        right=[ep(i*3+10,100,'b',i) for i in range(6)]
        from .bidirectional_association import associate as baseline
        base=baseline(left,right,PARAMS,blend=.5)
        got=associate(left,right,PARAMS)
        self.assertTrue({(m['left'],m['right']) for m in base}.issubset({(m['left'],m['right']) for m in got}))
        self.assertEqual(len(got),len({m['left'] for m in got}))
        self.assertEqual(len(got),len({m['right'] for m in got}))

    def test_namespacing_does_not_transfer_identity(self):
        site={'id':'A','tracks':[{'source_key':['session',1,'2']}]}
        a=annotate_endpoints([{'fragment':0}],site,{'assignments':['g0']})[0]
        b=annotate_endpoints([{'fragment':0}],dict(site,id='B'),{'assignments':['g0']})[0]
        self.assertNotEqual(a['local_identity'],b['local_identity'])

class FeatureVisibilityTests(unittest.TestCase):
    def test_hidden_points_and_full_track_summaries_never_reach_grouping(self):
        from .validate_between_groups import visible_track
        tr=dict(source_key=['s','x','2'],class_type='2',direction='eastbound',
                points=[[0,0,10],[1,10,10],[2,9999,99],[3,30,10],[4,40,10]],
                dimensions=[[2,4]]*5,movement={'movement':'WE'},
                lateral_start_m=888,lateral_end_m=999,
                lateral_start_context=[[0,1],[1,1],[2,999]],
                lateral_end_context=[[2,999],[3,1],[4,1]])
        left=visible_track(tr,{'t':1},True)
        right=visible_track(tr,{'t':3},False)
        self.assertEqual(left['points'],tr['points'][:2])
        self.assertEqual(right['points'],tr['points'][3:])
        self.assertNotIn('movement',left)
        self.assertEqual(left['lateral_end_m'],1)
        self.assertEqual(right['lateral_start_m'],1)
        self.assertEqual(len(left['dimensions']),2)

class AdapterReservationTests(unittest.TestCase):
    def test_residual_and_previous_group_endpoints_are_reserved(self):
        from .between_group_matching import build_additional
        import copy
        snapshot={'sites':[
            dict(id='A',name='A',station_m=0,tracks=[dict(source_key=['s','1','2'],class_type='2',direction='eastbound',points=[[0,0,10],[1,10,10],[2,20,10]])]),
            dict(id='B',name='B',station_m=100,tracks=[dict(source_key=['s','2','2'],class_type='2',direction='eastbound',points=[[12,120,10],[13,130,10],[14,140,10]])])
        ]}
        before=copy.deepcopy(snapshot)
        groups=[dict(id='A',assignments=['a']),dict(id='B',assignments=['b'])]
        def fake_reconstruct(snap,matcher,endpoint_enricher):
            left=[dict(site='A',fragment=0,t=2,x=20,v=10,class_type='2')]
            right=[dict(site='B',fragment=0,t=12,x=120,v=10,class_type='2')]
            matches=matcher(left,right)
            return {'links':[dict(sites=['A','B'],direction='eastbound',paths=[dict(upstream_fragment=0,downstream_fragment=0,association_cost=0,ambiguity_margin=1) for m in matches])]}
        proposed=[dict(left=0,right=0,cost=0,margin=1,points=[[2,20,10],[12,120,10]],group_assistance=True,group_evidence={'anchor_count':3})]
        with patch('deepctm.spatial_bridges.reconstruct',side_effect=fake_reconstruct), patch('deepctm.between_group_matching.associate',return_value=proposed), patch('deepctm.reconstruction_layers.prediction',return_value=[[2,20,10],[12,120,10]]):
            for key in ('residual_color','trajectory_groups'):
                existing={key:{'between_intersections':[dict(sites=['A','B'],points=[[2,20,10],[12,120,10]])]}}
                got=build_additional(snapshot,{'calibration':{'parameters':PARAMS}},existing,groups)
                self.assertEqual(got['paths'],[])
                self.assertEqual(got['diagnostics'][0]['existing_endpoint_reserved'],1)
            got=build_additional(snapshot,{'calibration':{'parameters':PARAMS}},{},groups)
            self.assertEqual(len(got['paths']),1)
            self.assertFalse(got['paths'][0]['cross_sensor_identity_verified'])
        self.assertEqual(snapshot,before)

if __name__=='__main__':unittest.main()
