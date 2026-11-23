import json,tempfile,unittest
from pathlib import Path
from dashboard.reconstruction_view import read

class ReconstructionViewTests(unittest.TestCase):
    def test_association_summary_excludes_internal_groups(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            (p/'status.json').write_text(json.dumps({'state':'evaluated_ablation','updated_at':80}))
            (p/'layers.json').write_text(json.dumps({'state':'ready','expires_at':200}))
            (p/'association-20261121.json').write_text(json.dumps({'state':'proxy_evaluated','test':{},'validation_groups':['internal']}))
            result=read(100,p)['association_validation']
            self.assertEqual(result['state'],'proxy_evaluated')
            self.assertNotIn('validation_groups',result)
    def test_no_completed_study_returns_waiting(self):
        with tempfile.TemporaryDirectory() as d:self.assertEqual(read(100,Path(d))['state'],'waiting')
    def test_expired_trajectories_not_returned(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'status.json').write_text(json.dumps({'state':'evaluated_ablation','updated_at':80,'report':'private/path'}));(p/'layers.json').write_text(json.dumps({'state':'ready','expires_at':99,'within_intersection':[{'points':[1,2]}]}))
            result=read(100,p);self.assertEqual(result['state'],'expired');self.assertNotIn('within_intersection',result);self.assertNotIn('report',result['study'])

    def test_simple_method_does_not_load_unrelated_archive(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            (p/'status.json').write_text(json.dumps({'state':'evaluated_ablation','updated_at':80}))
            (p/'layers.json').write_text(json.dumps({'state':'ready','expires_at':200,'method':'color_slope_chronological_v1','color_validation':{'summary':{}}}))
            (p/'association-20261121.json').write_text('not JSON')
            result=read(100,p)
            self.assertIn('color_validation',result)
            self.assertNotIn('association_validation',result)

    def test_bidirectional_validation_is_separate_from_old_study(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);p=root/'collection';p.mkdir();e=root/'bidirectional-review';e.mkdir()
            (p/'status.json').write_text(json.dumps({'state':'evaluated_ablation','updated_at':80}))
            (p/'layers.json').write_text(json.dumps({'state':'ready','expires_at':200,'association_method':'bidirectional_shape_v1'}))
            (e/'report.json').write_text(json.dumps({'state':'complete','test':{'0.5':{}},'limitations':['proxy only'],'deployment_eligible':True,'private_raw':'not returned'}))
            result=read(100,p)['bidirectional_validation']
            self.assertEqual(result['test'],{'0.5':{}})
            self.assertNotIn('private_raw',result)
