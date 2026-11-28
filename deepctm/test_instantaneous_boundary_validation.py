import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from .validate_instantaneous_boundary import evaluate, final, summary


class FakeEvidence:
    def __init__(self, *args):pass
    def observation(self, site, track, offset):
        return dict(timestamp='2026-11-24T18:00:00',lateral_m=0.)
    def close(self):pass


class BoundaryValidationTests(unittest.TestCase):
    def test_lateral_recovery_uses_actual_not_nominal_ten_second_duration(self):
        site={'id':'OBC-AG-SA-C251068'}
        track={'source_key':['s','one','2'],'class_type':'2'}
        left=[[0.,0.,1.],[10.,10.,1.]];right=[[20.5,20.5,1.],[25.,25.,1.]]
        a={'t':10.,'x':10.,'v':1.};b={'t':20.5,'x':20.5,'v':1.}
        case=('rank',site,track,10,'isolated',left,right,a,b,np.array([[15.,15.,1.]]),'eastbound',None)
        report={'calibration':{'parameters':{'vmax':25.,'amin':-6.,'amax':4.}}}
        with patch('deepctm.validate_instantaneous_boundary.local_cases',return_value=([case],[])),\
             patch('deepctm.validate_instantaneous_boundary.EndpointEvidence',FakeEvidence),\
             patch('deepctm.validate_instantaneous_boundary.candidates',return_value=[]) as admitted:
            result=evaluate({'start':0},'unused',report,{},0,100)
        self.assertEqual(admitted.call_count,1)
        self.assertFalse(result['cases'][0]['admitted'])
        self.assertEqual(result['cases'][0]['actual_gap_s'],10.5)

    def test_final_opened_marker_prevents_failed_test_reopening(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory)/'final_opened.json').write_text('{}')
            with self.assertRaisesRegex(ValueError,'already opened'):
                final('nonexistent_snapshot','nonexistent_buffer',directory)

    def test_joint_duration_counts_do_not_pool_unrelated_sites(self):
        metric=dict(mae_m=.1,rmse_m=.1,speed_mae_mps=.1,stop_time_error_s=0.,
                    physics_violation=0.,actual_stop=False,predicted_stop=False)
        rows=[]
        for i in range(10):
            rows.append(dict(site='a' if i<5 else 'b',identity_hash=str(i),admitted=True,gap_s=10,
                actual_gap_s=9.9 if i<5 else 10.1,mode='isolated',regime='moving',metrics={'retry':metric}))
        result=summary(rows,'retry')
        self.assertEqual(result['per_site_actual_duration_band']['a']['5-10']['independent_ids'],5)
        self.assertEqual(result['per_site_actual_duration_band']['a']['10-20']['independent_ids'],0)
        self.assertEqual(result['per_site_actual_duration_band']['b']['5-10']['independent_ids'],0)
        self.assertEqual(result['per_site_actual_duration_band']['b']['10-20']['independent_ids'],5)


if __name__=='__main__':unittest.main()
