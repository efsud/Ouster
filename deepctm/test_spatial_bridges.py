import unittest
import numpy as np
from .spatial_bridges import curve,associate
from .validate_spatial import masked

class SpatialTests(unittest.TestCase):
    def test_monotone_exact_endpoints_and_speed(self):
        a={'t':0,'x':0,'v':10};b={'t':10,'x':100,'v':10};p=curve(a,b)
        self.assertEqual(p[0][:2],[0,0]);self.assertEqual(p[-1][:2],[10,100]);self.assertTrue(all(abs(x[2]-10)<1e-8 for x in p))
    def test_westbound(self):
        p=curve({'t':0,'x':100,'v':-10},{'t':10,'x':0,'v':-10});self.assertTrue(all(b[1]<=a[1] for a,b in zip(p,p[1:])))
    def test_hidden_values_cannot_affect_boundary_inputs(self):
        tr={'direction':'eastbound','points':[[i*.5,i*2-100,4] for i in range(101)]};m=masked(tr,0,50)
        tr['points'][50][1]+=2;n=masked(tr,0,50)
        self.assertEqual(m[0],n[0]);self.assertEqual(m[1],n[1]);self.assertFalse(np.array_equal(m[2],n[2]))
    def test_ambiguous_matches_rejected(self):
        a={'t':0,'x':0,'v':10,'class_type':'1'};b={'t':10,'x':100,'v':10,'class_type':'1'}
        self.assertEqual(associate([a],[b,b]),[])
    def test_one_to_one(self):
        a=[{'t':t,'x':0,'v':10,'class_type':'1'} for t in [0,40]];b=[dict(x=100,t=e['t']+10,v=10,class_type='1') for e in a]
        m=associate(a,b);self.assertEqual([(r['left'],r['right']) for r in m],[(0,0),(1,1)])

    def test_queue_candidate_conserves_distance_and_has_stop(self):
        p=curve({'t':0,'x':0,'v':9},{'t':30,'x':100,'v':15},'queue')
        self.assertAlmostEqual(p[-1][1],100);self.assertAlmostEqual(p[0][2],9);self.assertAlmostEqual(p[-1][2],15)
        self.assertTrue(any(v==0 for t,x,v in p));self.assertTrue(all(b[1]>=a[1] for a,b in zip(p,p[1:])))
    def test_nonfinite_boundaries_rejected(self):
        self.assertIsNone(curve({'t':0,'x':float('nan'),'v':10},{'t':10,'x':100,'v':10}))
    def test_corridor_movement_gate_rejects_wrong_side_links(self):
        from dashboard.movements import route
        from deepctm.spatial_bridges import reconstruct
        def site(identifier,arrival,code):
            tracks=[]
            for i in range(10):
                points=[[40*i+(7 if arrival else 0)+j*.5,(100 if arrival else 30)+5*j,10] for j in range(5)]
                tracks.append({'direction':'eastbound','class_type':'1','points':points,'movement':{'movement':code,**route(code)}})
            return {'id':identifier,'name':identifier,'movement_summary':{},'tracks':tracks}
        def count(a,b):return sum(len(l['paths']) for l in reconstruct({'sites':[site('up',False,a),site('down',True,b)]})['links'])
        self.assertEqual(count('WE','WE'),10)
        self.assertEqual(count('NE','WN'),10)  # joins upstream, leaves downstream
        self.assertEqual(count('WN','WE'),0)   # already leaving upstream
        self.assertEqual(count('WE','NE'),0)   # newly joining downstream

class ResidualAssociationTests(unittest.TestCase):
    def test_feasible_filters_impossible_competitor_without_recursive_assignment(self):
        from unittest.mock import patch
        with patch('deepctm.spatial_bridges.pair_cost',return_value=.1),patch('deepctm.spatial_bridges.curve',side_effect=lambda a,b:None if b['id']==0 else [[0,0,1],[1,1,1]]):
            result=associate([{'id':0}],[{'id':0},{'id':1}],method='feasible')
        self.assertEqual([(r['left'],r['right']) for r in result],[(0,1)])
        costs={(0,0):.1,(1,0):.5,(1,1):.6};endpoints=[{'id':0},{'id':1}]
        with patch('deepctm.spatial_bridges.pair_cost',side_effect=lambda a,b:costs.get((a['id'],b['id']))),patch('deepctm.spatial_bridges.curve',return_value=[[0,0,1],[1,1,1]]):
            result=associate(endpoints,endpoints,method='feasible')
        self.assertEqual([(r['left'],r['right']) for r in result],[(0,0)])
    def test_resolves_competitor_after_its_endpoint_is_assigned(self):
        from unittest.mock import patch
        costs={(0,0):.1,(1,0):.5,(1,1):.6}
        endpoints=[{'id':0},{'id':1}]
        with patch('deepctm.spatial_bridges.pair_cost',side_effect=lambda a,b:costs.get((a['id'],b['id']))),patch('deepctm.spatial_bridges.curve',return_value=[[0,0,1],[1,1,1]]):
            result=associate(endpoints,endpoints,method='residual')
        self.assertEqual([(r['left'],r['right'],r['assignment_round']) for r in result],[(0,0,1),(1,1,2)])
    def test_equal_cost_ties_stay_unmatched(self):
        a={'t':0,'x':0,'v':10,'class_type':'1'};b={'t':10,'x':100,'v':10,'class_type':'1'}
        self.assertEqual(associate([a,a],[b,b],method='residual'),[])
    def test_impossible_curves_do_not_block_feasible_candidates(self):
        from unittest.mock import patch
        with patch('deepctm.spatial_bridges.pair_cost',return_value=.1),patch('deepctm.spatial_bridges.curve',side_effect=lambda a,b:None if b['id']==0 else [[0,0,1],[1,1,1]]):
            result=associate([{'id':0}],[{'id':0},{'id':1}],method='residual')
        self.assertEqual([(r['left'],r['right']) for r in result],[(0,1)])
    def test_augmented_preserves_baseline_and_never_reuses_endpoints(self):
        left=[{'t':40*i,'x':0,'v':10,'class_type':'1'} for i in range(12)]
        right=[dict(t=a['t']+10,x=100,v=10,class_type='1') for a in left]
        base=associate(left,right);new=associate(left,right,method='augmented')
        self.assertTrue({(m['left'],m['right']) for m in base}<={(m['left'],m['right']) for m in new})
        self.assertEqual(len(new),len({m['left'] for m in new}));self.assertEqual(len(new),len({m['right'] for m in new}))
