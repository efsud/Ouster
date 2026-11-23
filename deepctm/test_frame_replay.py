import unittest,json
from datetime import datetime,timezone
from .florida_rolling import build,connect
class ReplayTests(unittest.TestCase):
    def test_identical_replay_does_not_break_track_or_erase_raw_count(self):
        d=connect(':memory:')
        for i in range(20):
            t=1000+i*.5
            raw=json.dumps({'timestamp':datetime.fromtimestamp(t,timezone.utc).isoformat(),'frame':{'objects':[{'id':'car','classType':'2','centerX':i,'centerY':0}]}})
            for replay in range(2):d.execute('insert into frames values(?,?,?,?,?)',('site','session',f'{i}-{replay}',t+replay*.01,raw))
        d.commit();s={'id':'site','name':'site','region':'Florida','reference_location':{'lat':0,'lng':0},'preview_rotation_deg':0}
        result=build(d,[s],1100)['sites'][0];d.close()
        self.assertEqual(result['raw_frames'],40);self.assertEqual(result['duplicate_frame_payloads'],20)
        self.assertEqual(len(result['tracks']),1);self.assertEqual(len(result['tracks'][0]['points']),20)
