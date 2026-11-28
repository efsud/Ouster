import unittest
import numpy as np
from .observed_flow_prior import envelope
from .validate_integration import hide_context

class ObservedFlowTests(unittest.TestCase):
    def fixture(self):
        target={'source_key':['s','target','2'],'direction':'eastbound','lateral_start_m':0}
        tracks=[dict(target,source_key=['s',str(n),'2'],class_type='2',lateral_end_m=0,
                     points=[[float(t),float(t)*2+n*4,2] for t in np.arange(-2,22,.5)]) for n in range(1,4)]
        return target,{'station_m':0,'tracks':tracks},dict(t=0,x=0,v=2),dict(t=20,x=40,v=2),dict(vmax=25,amin=-4,amax=3)
    def test_observed_other_vehicles_support_field(self):
        target,site,a,b,params=self.fixture();e,info=envelope(site,target,a,b,params)
        self.assertGreater(info['supported_samples'],30)
        self.assertTrue(np.all(e[:,1]<=2));self.assertTrue(np.all(e[:,2]>=2))
    def test_outage_removes_interior_support(self):
        target,site,a,b,params=self.fixture();hidden=hide_context(site,target,a,b,'outage')
        e,info=envelope(hidden,target,a,b,params)
        self.assertEqual(info['supported_samples'],0)
    def test_target_fragments_do_not_count_as_neighbors(self):
        target,site,a,b,params=self.fixture()
        for tr in site['tracks']:tr['source_key']=['s','target','2']
        _,info=envelope(site,target,a,b,params);self.assertEqual(info['supported_samples'],0)
