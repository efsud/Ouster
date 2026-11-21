import unittest
from deepctm.rolling_estimates import step,estimate,features,gap_validation,JAM
class RollingEstimatesTest(unittest.TestCase):
    def test_conservation_and_jam_bounds(self):
        k=[0,.01,.10,.29,.30]
        for _ in range(600):
            k,speed,error=step(k,1.2,.28,30,20)
            self.assertLess(error,1e-10)
            self.assertTrue(all(-1e-12<=v<=JAM+1e-12 for v in k))
            self.assertTrue(all(0<=v<=20 for v in speed))
    def site(self,name,station):
        return dict(id=name,name=name,station_m=station,coverage=[1.]*60,
          tracks=[dict(class_type='1',direction='eastbound',points=[[t,station-100+(t-base)*10,10] for t in range(base,base+23)]) for base in range(0,3600-23,10)])
    def test_supported_paths_and_missing_site(self):
        a,b=self.site('a',0),self.site('b',500)
        result=estimate({'sites':[a,b]});link=result['links'][0]
        self.assertTrue(link['paths']);self.assertLess(link['max_mass_error_vehicles'],1e-9)
        for path in link['paths']:
            self.assertLessEqual(path['points'][-1][1],380.01)
            self.assertTrue(all(y[0]>x[0] and y[1]>=x[1] for x,y in zip(path['points'],path['points'][1:])))
        b['coverage']=[0.]*60
        self.assertTrue(all(not l['paths'] for l in estimate({'sites':[a,b]})['links']))
    def test_no_overlap_or_pedestrian_model(self):
        a,b=self.site('a',0),self.site('b',200)
        self.assertEqual(estimate({'sites':[a,b]})['links'],[])
        for t in a['tracks']:t['class_type']='10'
        self.assertFalse(any(f['valid'] for f in features(a,'eastbound')))
    def test_masked_constant_speed(self):
        r=gap_validation({'sites':[self.site('a',0)]})
        self.assertGreater(r['count'],0);self.assertAlmostEqual(r['interpolation_mae_m'],0)
