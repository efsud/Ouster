import unittest
from dashboard.finch_groups import evaluate_history,snapshot
class FinchGroupsTest(unittest.TestCase):
    def rows(self):
        return [{'receipt':i,'session':'s','phases':{'1':('GREEN' if i%100<40 else 'YELLOW' if i%100<45 else 'RED'),'11':('GREEN' if i%100<40 else 'YELLOW' if i%100<45 else 'RED')}} for i in range(301)]
    def test_repeated_cycles_allow_only_identical_groups(self):
        rows=self.rows();self.assertTrue(evaluate_history(rows,['1','11'])['eligible'])
        rows[80]['phases']['11']='GREEN'
        self.assertFalse(evaluate_history(rows,['1','11'])['eligible'])
        self.assertTrue(evaluate_history(rows,['1'])['eligible'])
    def test_missing_channels_and_reconnects_do_not_qualify(self):
        self.assertFalse(evaluate_history(self.rows(),['9'])['eligible'])
        rows=self.rows();rows[-1]['session']='new'
        self.assertFalse(evaluate_history(rows,['1'])['eligible'])
        rows=self.rows();rows[-1]['receipt']=400
        self.assertFalse(evaluate_history(rows,['1'])['eligible'])
    def test_florida_excluded(self):
        self.assertEqual(snapshot({'region':'Florida'},{},{},{}),[])
    def test_placement_needs_fresh_vehicle_support_and_matching_session(self):
        import tempfile,json,time
        from pathlib import Path
        from unittest.mock import patch
        now=time.time()
        with tempfile.TemporaryDirectory() as tmp:
            config=Path(tmp)/'config.json'
            config.write_text(json.dumps({'sites':{'S':[{'labels':['4'],'associations':[{'movement':'SN','statuses':['G']}]}]}}))
            evidence={'updated_at':now,'sites':{'S':{'session':'s','history':{'4':{'eligible':True}}}}}
            phases={'phases':[{'phase':'4','status':'GREEN'}]}
            estimate={'session':'s','updated_at':now,'last_receipt':now,'directions':{'N':{'candidates':[{'phase':'4','releases':10,'release_cycles':3,'green_fraction':1,'onset_fraction':1}]}}}
            with patch('dashboard.finch_groups.CONFIG',config):
                site={'id':'S','region':'Toronto'}
                self.assertFalse(snapshot(site,phases,evidence,{},'s')[0]['show_on_map'])
                self.assertTrue(snapshot(site,phases,evidence,estimate,'s')[0]['show_on_map'])
                self.assertFalse(snapshot(site,phases,evidence,estimate,'new')[0]['show_on_map'])
                estimate['directions']['S']=estimate['directions']['N']
                self.assertFalse(snapshot(site,phases,evidence,estimate,'s')[0]['show_on_map'])
