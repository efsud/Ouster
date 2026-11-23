import unittest
import numpy as np
from .partial_leader import reference
from .trajectory_reconstruction import baseline
from .validate_integration import hide_context

class PartialLeaderTests(unittest.TestCase):
    def fixture(self):
        target={'source_key':['s','target','2'],'direction':'eastbound','lateral_start_m':0}
        other=dict(target,source_key=['s','leader','2'],class_type='2',lateral_end_m=0,
                   points=[[float(t),10+float(t)*2,2] for t in np.arange(-2,13,.5)])
        return target,{'station_m':0,'tracks':[other]},dict(t=0,x=0,v=2),dict(t=20,x=100,v=10),dict(vmax=25,amin=-4,amax=3)
    def test_supported_prefix_without_extrapolation(self):
        target,site,a,b,params=self.fixture();p,e=reference(site,target,a,b,params);original=baseline(a,b)
        self.assertTrue(e['used']);self.assertGreater(e['support_s'],5)
        np.testing.assert_allclose(p[p[:,0]>14,1],original[original[:,0]>14,1])
        self.assertEqual(p[0,1],a['x']);self.assertEqual(p[-1,1],b['x'])
    def test_outage_cannot_use_hidden_leader(self):
        target,site,a,b,params=self.fixture()
        p,e=reference(hide_context(site,target,a,b,'outage'),target,a,b,params)
        self.assertFalse(e['used'])
    def test_ambiguous_leaders_withheld(self):
        target,site,a,b,params=self.fixture();other=site['tracks'][0]
        site['tracks'].append(dict(other,source_key=['s','parallel','2'],points=[[t,x+1,v] for t,x,v in other['points']]))
        _,e=reference(site,target,a,b,params);self.assertFalse(e['used'])
