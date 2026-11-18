import unittest,tempfile,json
from datetime import datetime,timezone
from pathlib import Path
from deepctm.local_gaps import bridge
from deepctm.florida_rolling import build,connect

def p(t,x=None,y=0):
    return (t,t*2 if x is None else x,y,2,datetime.fromtimestamp(t,timezone.utc))

class LocalGapTest(unittest.TestCase):
    def test_constant_speed_endpoints_and_limits(self):
        r=bridge([p(t) for t in range(5)],[p(t) for t in range(10,15)])
        self.assertIsNotNone(r);self.assertEqual(r[0][:2],[4,8]);self.assertEqual(r[-1][:2],[10,20])
        self.assertTrue(all(abs(v-2)<1e-8 for _,_,v in r))
        self.assertIsNone(bridge([p(t) for t in range(5)],[p(t) for t in range(40,45)]))
    def test_rejects_reversal_jump_lateral_and_clock(self):
        before=[p(t) for t in range(5)]
        self.assertIsNone(bridge(before,[p(t,40-t) for t in range(10,15)]))
        self.assertIsNone(bridge(before,[p(t,t*2,7) for t in range(10,15)]))
        self.assertIsNone(bridge(before,[p(t,t*2+70) for t in range(10,15)]))
        after=[tuple(list(p(t))[:4]+[datetime.fromtimestamp(t+100,timezone.utc)]) for t in range(10,15)]
        self.assertIsNone(bridge(before,after))
    def test_build_isolates_session_and_object(self):
        sites=[{'id':'S','name':'S','reference_location':{'lat':28,'lng':-81},'preview_rotation_deg':0}]
        for session,oid,expected in [('a','1',1),('b','1',0),('a','2',0)]:
            with tempfile.TemporaryDirectory() as tmp:
                db=connect(Path(tmp)/'db')
                for i in list(range(5))+list(range(10,15)):
                    t=8000+i;e={'timestamp':datetime.fromtimestamp(t,timezone.utc).isoformat(),'frame':{'objects':[{'id':'1' if i<5 else oid,'classType':1,'centerX':i*2,'centerY':0}]}}
                    db.execute('INSERT INTO frames VALUES(?,?,?,?,?)',('S','a' if i<5 else session,str(t),t,json.dumps(e)))
                db.commit();r=build(db,sites,10000)
                self.assertEqual(len(r['sites'][0]['local_estimates']),expected)
                db.close()
