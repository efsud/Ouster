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
