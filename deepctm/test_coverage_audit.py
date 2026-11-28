import copy
import unittest
from .coverage_audit import audit


class CoverageTests(unittest.TestCase):
    def test_gap_conservation_and_unknown_not_exit(self):
        points=[[i*.5,float(i),2.] for i in range(10)]
        second=[[10+i*.5,20.+i,2.] for i in range(10)]
        def track(p):
            return dict(points=p,source_key=['session','id','2'],class_type='2',direction='eastbound')
        site=dict(id='A',name='A',tracks=[track(points),track(second)])
        snapshot=dict(generated_at=1,sites=[site])
        layers=dict(within_intersection=[],between_intersections=[])
        before=copy.deepcopy(snapshot)
        row=audit(snapshot,layers)['sites'][0]
        self.assertEqual(row['observable_same_id_gaps'],1)
        self.assertEqual(row['unresolved'],1)
        self.assertEqual(row['movement_roles'],{'unknown':2})
        path=dict(site='A',identity_key=['session','id'],points=[points[-1],second[0]])
        layers['within_intersection']=[path]
        row=audit(snapshot,layers)['sites'][0]
        self.assertEqual(row['baseline_estimated'],1)
        self.assertEqual(row['unresolved'],0)
        self.assertEqual(snapshot,before)

    def test_coincident_other_identity_does_not_cover_gap(self):
        s=dict(generated_at=1,sites=[dict(id='A',name='A',tracks=[dict(
            class_type='2',source_key=['s','one','2'],direction='eastbound',
            points=[[0,0,0],[4,0,0]])])])
        p=dict(site='A',identity_key=['s','other'],points=[[0,0,0],[4,0,0]])
        result=audit(s,dict(within_intersection=[p]))
        self.assertEqual(result['sites'][0]['unresolved'],1)

    def test_experiments_do_not_reduce_baseline_unmatched_counts(self):
        link=dict(sites=['A','B'],names=['A','B'],direction='eastbound',departure_candidates=5,arrival_candidates=4)
        p=dict(sites=['A','B'],direction='eastbound')
        result=audit(dict(sites=[],generated_at=1),dict(association_diagnostics=[link],
            between_intersections=[p],residual_color={'between_intersections':[p]}))
        self.assertEqual(result['links'][0]['baseline_unmatched_departures'],4)
        self.assertEqual(result['links'][0]['experimental_estimated'],1)


if __name__=='__main__':unittest.main()
