import json,tempfile,unittest
from pathlib import Path
from dashboard.reconstruction_view import read

class ReconstructionViewTests(unittest.TestCase):
    def test_completed_candidate_review_is_separate_and_sanitized(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);p=root/'collection';p.mkdir();e=root/'two-phase-review-20261124';e.mkdir()
            (p/'status.json').write_text(json.dumps({'state':'evaluated_ablation'}))
            (p/'layers.json').write_text(json.dumps({'state':'ready','expires_at':200,'association_method':'bidirectional_shape_v1'}))
            report={'state':'complete','title':'Candidate withheld','window':[1,2],'lines':['Wrong matches increased; current method retained.'],'raw_cases':['private']}
            (e/'summary.json').write_text(json.dumps(report))
            result=read(100,p)
            self.assertEqual(result['association_method'],'bidirectional_shape_v1')
            self.assertEqual(result['two_phase_review']['title'],'Candidate withheld')
            self.assertNotIn('raw_cases',result['two_phase_review'])
            report['state']='running';(e/'summary.json').write_text(json.dumps(report))
            self.assertNotIn('two_phase_review',read(100,p))
            finch=root/'finch';finch.mkdir()
            for name in ('status.json','layers.json'):(finch/name).write_text((p/name).read_text())
            report['state']='complete';(e/'summary.json').write_text(json.dumps(report))
            self.assertNotIn('two_phase_review',read(100,finch))
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

    def test_local_lateral_evidence_requires_active_layer(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);p=root/'collection';p.mkdir();e=root/'local-lateral-review';e.mkdir()
            (p/'status.json').write_text(json.dumps({'state':'evaluated_ablation','updated_at':80}))
            (e/'deployment.json').write_text(json.dumps({'enabled_sites':['site'],'test':{'accepted':109}}))
            (p/'layers.json').write_text(json.dumps({'state':'ready','expires_at':200,'local_lateral':True}))
            self.assertEqual(read(100,p)['local_lateral_validation']['test']['accepted'],109)
            (p/'layers.json').write_text(json.dumps({'state':'ready','expires_at':200,'local_lateral':False}))
            self.assertIsNone(read(100,p)['local_lateral_validation'])
