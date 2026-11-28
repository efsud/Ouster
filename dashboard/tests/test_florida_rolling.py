import json,tempfile,unittest
from pathlib import Path
from datetime import datetime,timezone
from unittest.mock import patch
from deepctm.florida_rolling import connect,purge,build,read_snapshot

class FloridaRollingTest(unittest.TestCase):
    def test_retention_and_deduplication(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=connect(Path(tmp)/'db')
            for t in [4599,4600,9999]:
                for _ in range(2):db.execute('INSERT OR IGNORE INTO frames VALUES(?,?,?,?,?)',('S','a',str(t),t,'{}'))
            purge(db,10000)
            self.assertEqual([r[0] for r in db.execute('select received from frames order by received')],[4600,9999])
            db.close()
    def test_window_and_session_isolation(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=connect(Path(tmp)/'db')
            for session,base in [('old',1000),('new',8000),('another',8010)]:
                for i in range(4):
                    t=base+i;e={'timestamp':datetime.fromtimestamp(t,timezone.utc).isoformat(),'frame':{'objects':[{'id':'1','classType':1,'centerX':i*5,'centerY':0}]}}
                    db.execute('INSERT INTO frames VALUES(?,?,?,?,?)',('S',session,str(t),t,json.dumps(e)))
            db.commit()
            result=build(db,[{'id':'S','name':'S','reference_location':{'lat':28,'lng':-81},'preview_rotation_deg':0}],10000)
            self.assertEqual((result['start'],result['end'],result['next_update']),(6400,10000,11800))
            self.assertEqual(len(result['sites'][0]['tracks']),2)
            self.assertEqual(result['sites'][0]['frames'],8)
            self.assertTrue(all(0<=p[0]<=3600 for t in result['sites'][0]['tracks'] for p in t['points']))
            db.close()
    def test_snapshot_expires_at_retention_horizon(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp);(path/'snapshot.json').write_text(json.dumps({'start':1000}))
            with patch('deepctm.florida_rolling.FOLDER',path):
                self.assertEqual(read_snapshot(6400)['state'],'ready')
                self.assertEqual(read_snapshot(6401)['state'],'expired')
