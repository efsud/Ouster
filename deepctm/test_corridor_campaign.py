import json,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
from .corridor_campaign import identity,earlier_ids,sample,evaluate,run,aggregate

class CampaignTests(unittest.TestCase):
    def tr(self,session='a',id='1',cls='2',start=0):
        return {'source_key':[session,id,cls],'class_type':cls,'points':[[start,0,1],[start+20,20,1]]}
    def test_identity_excludes_class_but_includes_site_session(self):
        site={'id':'A'}
        self.assertEqual(identity(site,self.tr()),identity(site,self.tr(cls='3')))
        self.assertNotEqual(identity(site,self.tr()),identity(site,self.tr(session='b')))
        self.assertNotEqual(identity(site,self.tr()),identity({'id':'B'},self.tr()))
    def test_training_id_cannot_reenter_validation_with_different_class(self):
        first=self.tr();later=self.tr(cls='3',start=100);other=self.tr(id='2',start=100)
        s={'sites':[{'id':'A','tracks':[first,later,other]}]}
        excluded=earlier_ids(s,50)
        with patch('deepctm.corridor_campaign.cases',side_effect=lambda s,*a:s) as mock:
            result=sample(s,90,150,excluded=excluded)
        self.assertEqual(result['sites'][0]['tracks'],[other])
    def test_expired_deadline_does_no_fitting(self):
        with tempfile.TemporaryDirectory() as folder,patch('deepctm.corridor_campaign.calibrate') as calibrate:
            run(folder,time.time()-1)
            self.assertFalse(calibrate.called)
            self.assertEqual(json.loads((Path(folder)/'status.json').read_text())['state'],'complete')
    def test_deadline_stops_before_solver(self):
        with patch('deepctm.corridor_campaign.reconstruct') as solver:
            result=evaluate([None],{},time.time()-1)
            self.assertFalse(solver.called)
            self.assertEqual(result['summary']['strict']['evaluated'],0)

    def test_aggregate_does_not_count_unmatched_as_recovered(self):
        with tempfile.TemporaryDirectory() as folder:
            region=Path(folder)/'finch';region.mkdir()
            result={'results':{'summary':{m:{'evaluated':3} for m in ('strict','noise')},'cases':[]}}
            (region/'cycle-001.json').write_text(json.dumps(result))
            total=aggregate(folder,complete=True)
            self.assertEqual(total['regions']['finch']['methods']['strict']['eligible'],3)
            self.assertEqual(total['regions']['finch']['methods']['strict']['accepted'],0)
            self.assertEqual(total['state'],'complete')
