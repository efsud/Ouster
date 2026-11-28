import unittest
import numpy as np
from .movement_queue import simulate
from .integrated_reconstruction import context,reconstruct
from .validate_integration import hide_context

class IntegrationTests(unittest.TestCase):
    def test_estimated_internal_red_conserves_mass(self):
        factors=np.ones((10,4));factors[:,2]=0
        r=simulate([.1,.1,.1],[20]*3,1,15,5,.2,[.1]*10,[.5]*10,estimated_capacity_factors=factors)
        self.assertLess(r['max_mass_error_vehicles'],1e-10)
        self.assertTrue(np.all(r['flow'][:,2]==0))
        self.assertEqual(r['capacity_evidence'],'estimated_scenario_not_permission')
        self.assertNotEqual(r['signal_state'],'verified')
    def test_excludes_target_including_other_fragments(self):
        tr={'source_key':['s','id','2'],'direction':'eastbound','lateral_start_m':0,'lateral_end_m':0,'class_type':'2','points':[[0,0,10],[1,10,10]]}
        site={'station_m':0,'tracks':[tr,dict(tr,source_key=['s','id','4'])]}
        other,leader,center=context(site,tr,dict(t=0,x=0),dict(t=1,x=10))
        self.assertEqual(other,[]);self.assertIsNone(leader)
    def test_outage_and_spatial_mask_all_other_vehicles(self):
        tr={'source_key':['s','id','2']};other={'source_key':['s','other','2'],'points':[[0,0,1],[1,1,1],[2,2,1],[3,3,1]]}
        site={'tracks':[other]};a={'t':0};b={'t':3}
        for kind,band in [('outage',None),('spatial',(.5,2.5))]:
            result=hide_context(site,tr,a,b,kind,band)
            self.assertEqual(result['tracks'][0]['points'],[[0,0,1],[3,3,1]])
    def test_missing_signal_and_leader_remain_explicit(self):
        tr={'source_key':['s','id','2'],'direction':'eastbound','lateral_start_m':0}
        r=reconstruct({'station_m':0,'tracks':[]},tr,dict(t=0,x=0,v=10),dict(t=5,x=50,v=10),{'vmax':20,'amin':-4,'amax':3})
        self.assertEqual(r['state'],'candidate');self.assertFalse(r['leader_used']);self.assertFalse(r['signal_used'])
        self.assertIn('signal_mapping_unavailable',r['flags'])
