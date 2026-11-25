import copy
import unittest
from .same_id_continuity import apply, connect, curve, extend


def track(start,end,offset=0,cls='2',session='s',identity='v'):
    from datetime import datetime,timedelta
    return dict(source_key=[session,identity,cls],class_type=cls,direction='eastbound',
        points=[[t,10*t+offset,10] for t in range(start,end+1)],
        sensor_start=(datetime(2026,1,1)+timedelta(seconds=start)).isoformat(),
        sensor_end=(datetime(2026,1,1)+timedelta(seconds=end)).isoformat(),
        lateral_start_m=0,lateral_end_m=0)


class SameIdContinuityTests(unittest.TestCase):
    def test_class_change_long_gap_and_lateral_motion_connect_without_mutation(self):
        a,b=track(0,3),track(63,66,cls='3');b['lateral_start_m']=5
        snapshot={'sites':[dict(id='A',name='A',tracks=[a,b])], 'generated_at':1}
        original=copy.deepcopy(snapshot)
        paths,review=extend(snapshot,[])
        self.assertEqual(len(paths),1);self.assertEqual(snapshot,original)
        self.assertTrue(paths[0]['classification_changed'])
        self.assertIn('long_gap_motion_unobserved',paths[0]['warnings'])
        self.assertEqual(paths[0]['points'][0][:2],a['points'][-1][:2])
        self.assertEqual(paths[0]['points'][-1][:2],b['points'][0][:2])
        self.assertFalse(paths[0]['kpi_eligible'])

    def test_site_session_and_id_scopes_never_cross(self):
        a=track(0,3);b=track(8,11,session='other');c=track(8,11,identity='other')
        paths,_=extend({'sites':[dict(id='A',name='A',tracks=[a,b,c]),dict(id='B',name='B',tracks=[track(8,11)])]},[])
        self.assertEqual(paths,[])

    def test_timing_conflict_connects_without_speed_claim_and_reset_rejects(self):
        a,b=track(0,3),track(8,11)
        b['sensor_start']='2026-01-01T00:00:03.100000'
        path,reason=connect(a,b)
        self.assertIsNone(reason);self.assertTrue(path['timing_uncertain']);self.assertFalse(path['speed_available'])
        b['sensor_start']='2025-12-31T23:00:00'
        self.assertEqual(connect(a,b)[1],'sensor_clock_reset_or_reordered_identity')

    def test_duplicate_endpoint_recovery_is_idempotent(self):
        snapshot={'sites':[dict(id='A',name='A',tracks=[track(0,3),track(8,11)])]}
        first,_=extend(snapshot,[]);second,review=extend(snapshot,first)
        self.assertEqual(first,second);self.assertEqual(review['added'],0)

    def test_rejects_teleportation_and_opposing_direction(self):
        a,b=track(0,3),track(8,11,offset=1000)
        self.assertEqual(connect(a,b)[1],'impossible_average_displacement')
        b=track(8,11);b['direction']='westbound'
        self.assertEqual(connect(a,b)[1],'conflicting_travel_directions')

    def test_limited_tangents_are_bounded_and_hit_endpoints(self):
        for a,b,v0,v1 in [([0,0],[8,15],20,-3),([0,100],[30,0],-20,-20),([0,0],[200,.1],-.1,.1)]:
            points,_=curve(a,b,v0,v1)
            self.assertEqual(points[0][:2],a);self.assertEqual(points[-1][:2],b)
            self.assertTrue(all(0<=p[2]<=35.00001 for p in points))
            self.assertTrue(all(min(a[1],b[1])-1e-8<=p[1]<=max(a[1],b[1])+1e-8 for p in points))
            self.assertTrue(all(abs((q[2]-p[2])/(q[0]-p[0]))<=4.00001 for p,q in zip(points,points[1:])))

    def test_internal_gaps_and_short_class_breaks(self):
        a=track(0,9);a['points']=a['points'][:3]+a['points'][6:]
        paths,_=extend({'sites':[dict(id='A',name='A',tracks=[a])]},[])
        self.assertEqual(len(paths),1);self.assertEqual(paths[0]['gap_kind'],'internal_sampling_gap')
        a,b=track(0,3),track(4,8,cls='3')
        self.assertIsNotNone(connect(a,b)[0])

    def test_nonvehicle_fragment_is_not_skipped_to_bridge_over_observations(self):
        tracks=[track(0,3),track(5,8,cls='10'),track(10,13)]
        paths,_=extend({'sites':[dict(id='A',name='A',tracks=tracks)]},[])
        self.assertEqual(len(paths),2)
        self.assertFalse(any(p['points'][0][0]==3 and p['points'][-1][0]==10 for p in paths))

    def test_nested_observation_is_not_mistaken_for_a_missing_interval(self):
        tracks=[track(0,10),track(5,7,cls='3'),track(15,20)]
        paths,_=extend({'sites':[dict(id='A',name='A',tracks=tracks)]},[])
        self.assertEqual(len(paths),1)
        self.assertEqual((paths[0]['points'][0][0],paths[0]['points'][-1][0]),(10,15))

    def test_internal_endpoints_cannot_also_depart_to_another_site(self):
        a,b=track(0,3),track(8,11)
        snapshot={'sites':[dict(id='A',name='A',tracks=[a,b])],'generated_at':1}
        crossing={'sites':['A','B'],'points':[[3,30,10],[7,70,10]],'endpoint_provenance':{
            'departure':dict(site='A',source_key=a['source_key'],observed_endpoint=a['points'][-1])}}
        baseline={'within_intersection':[],'between_intersections':[crossing]}
        result=apply(snapshot,baseline)
        self.assertEqual(result['between_intersections'],[])
        self.assertEqual(len(baseline['between_intersections']),1)


if __name__=='__main__':unittest.main()
