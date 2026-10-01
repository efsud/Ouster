import json,sqlite3,unittest
from scripts.audit_signal_mapping import audit

class SignalMappingAuditTest(unittest.TestCase):
    def test_duplicate_phase_evidence_never_becomes_physical_head_count(self):
        db=sqlite3.connect(':memory:')
        db.execute('CREATE TABLE raw_events(site,session,received_at,payload,sequence)')
        db.execute('CREATE INDEX raw_site_receipt ON raw_events(site,received_at)')
        for i in range(20):
            status=1 if i<10 else 3
            e={'timestamp':f'2026-01-01T00:00:{i:02d}','phaseChange':{'absolute':True,'phases':[{'phaseNumber':str(n),'status':status if n in [1,2] else 3 if n in [3,4] else 0} for n in range(1,6)]},'frame':{'objects':[]}}
            db.execute('INSERT INTO raw_events VALUES(?,?,?,?,?)',('S','a',100+i,json.dumps(e),i))
        r=audit(db,'S')
        self.assertEqual(r['identical_observed_state_groups'],[['1','2']])
        self.assertEqual(r['invalid_only_ids'],['5'])
        self.assertIsNone(r['physical_head_count']);self.assertFalse(r['verified_phase_mapping'])
        self.assertEqual(r['candidate_areas'],[])
        self.assertTrue(audit(db,'missing')['no_data'])
