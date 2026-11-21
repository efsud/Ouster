import unittest
from .global_association import solve_edges, associate_global


class GlobalAssociationTests(unittest.TestCase):
    def test_global_alternative_not_greedy(self):
        # Greedy takes .1 + 1.4; joint optimum is .2 + .2.
        matches = solve_edges(2, 2, {(0,0):.1, (0,1):.2, (1,0):.2, (1,1):1.4})
        self.assertEqual([(m['left'],m['right']) for m in matches], [(0,1),(1,0)])
        self.assertTrue(all(abs(m['margin']-1.1)<1e-8 for m in matches))

    def test_ties_and_unmatched_alternative(self):
        self.assertEqual(solve_edges(2,2,{(i,j):.1 for i in range(2) for j in range(2)}), [])
        self.assertEqual(solve_edges(1,1,{(0,0):1.4}), [])
        self.assertEqual(solve_edges(1,1,{(0,0):2}), [])

    def test_unbalanced_components_and_reordering(self):
        result = solve_edges(3,2,{(0,0):.1,(2,1):.2})
        self.assertEqual([(m['left'],m['right']) for m in result],[(0,0),(2,1)])
        reverse = solve_edges(3,2,{(2,1):.1,(0,0):.2})
        self.assertEqual({(2-m['left'],1-m['right']) for m in reverse},{(0,0),(2,1)})

    def test_class_and_physical_gates(self):
        a = dict(t=0,x=0,v=10,class_type='2')
        b = dict(t=10,x=100,v=10,class_type='2')
        self.assertEqual(len(associate_global([a],[b])),1)
        self.assertEqual(associate_global([a],[dict(b,class_type='3')]),[])
        self.assertEqual(associate_global([a],[dict(b,t=1)]),[])

    def test_invalid_cost(self):
        with self.assertRaises(ValueError):
            solve_edges(1,1,{(0,0):float('nan')})
