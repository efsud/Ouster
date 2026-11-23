import unittest,sqlite3,json
from datetime import datetime,timedelta
from .florida_rolling import build,connect
class RollingTimeBasisTests(unittest.TestCase):
    def test_moderate_delivery_is_site_opt_in(self):
        db=connect(':memory:');stamp=datetime(2026,1,1)
        for i in range(300):
            t=i*.1;receipt=1000+t+(max(0,.8-(i-80)*.01) if 80<=i<160 else 0)
            raw={'frame':{'timestamp':(stamp+timedelta(seconds=t)).isoformat(),'objects':[{'id':'car','classType':'2','centerX':t,'centerY':0}]}}
            db.execute('insert into frames values(?,?,?,?,?)',('site','session',str(i),receipt,json.dumps(raw)))
        db.commit();rows=db.execute('select * from frames order by received').fetchall()
        site={'id':'site','name':'site','region':'Florida','reference_location':{'lat':0,'lng':0},'preview_rotation_deg':0}
        old=build(db,[site],1030,time_basis='receipt_debursted',moderate_timing_sites=['other'])
        new=build(db,[site],1030,time_basis='receipt_debursted',moderate_timing_sites=['site'])
        self.assertEqual(old['sites'][0]['clock_audit'][0]['corrected_frames'],0)
        self.assertGreater(new['sites'][0]['clock_audit'][0]['corrected_frames'],0)
        self.assertEqual(new['moderate_timing_sites'],['site'])
        self.assertEqual(db.execute('select * from frames order by received').fetchall(),rows)
        db.close()
    def test_bounded_delivery_correction_keeps_raw_receipts(self):
        db=connect(':memory:');stamp=datetime(2026,1,1)
        for i in range(300):
            t=i*.1;receipt=1000+t+(max(0,5-(i-80)*.05) if 80<=i<180 else 0)
            raw={'frame':{'timestamp':(stamp+timedelta(seconds=t)).isoformat(),'objects':[{'id':'car','classType':'2','centerX':t,'centerY':0,'width':2,'length':4}]}}
            db.execute('insert into frames values(?,?,?,?,?)',('site','session',str(i),receipt,json.dumps(raw)))
        db.commit();site={'id':'site','name':'site','region':'Florida','reference_location':{'lat':0,'lng':0},'preview_rotation_deg':0}
        result=build(db,[site],1030,time_basis='receipt_debursted')
        self.assertEqual(db.execute('select count(*) from frames').fetchone()[0],300)
        self.assertEqual(result['sites'][0]['raw_frames'],300)
        self.assertGreater(result['sites'][0]['clock_audit'][0]['corrected_frames'],0)
        longest=max(result['sites'][0]['tracks'],key=lambda t:len(t['points']))
        self.assertEqual(len(longest['points']),300)
        self.assertTrue(any(abs(raw-p[0])>3 for raw,p in zip(longest['original_receipt_offsets_s'],longest['points'])))
        db.close()
    def test_sensor_timeline_preserves_original_receipts_and_sizes(self):
        db=connect(':memory:');stamp=datetime(2026,1,1);previous=0
        for i in range(400):
            t=i*.5;receipt=max(1000+t+(4 if i==160 else 0),previous+.01);previous=receipt
            raw={'frame':{'timestamp':(stamp+timedelta(seconds=t)).isoformat(),'objects':[{'id':'car','classType':'2','centerX':t-100,'centerY':0,'width':2,'length':4}]}}
            db.execute('insert into frames values(?,?,?,?,?)',('site','session',str(i),receipt,json.dumps(raw)))
        db.commit();site={'id':'site','name':'site','region':'Florida','reference_location':{'lat':0,'lng':0},'preview_rotation_deg':0}
        result=build(db,[site],1200,time_basis='sensor_elapsed');db.close()
        self.assertEqual(result['time_basis'],'sensor_elapsed');s=result['sites'][0]
        self.assertEqual(s['raw_frames'],400);self.assertEqual(s['clock_audit'][0]['state'],'candidate')
        track=max(s['tracks'],key=lambda t:len(t['points']))
        self.assertEqual(len(track['points']),len(track['original_receipt_offsets_s']))
        self.assertTrue(any(abs(raw-p[0])>3 for raw,p in zip(track['original_receipt_offsets_s'],track['points'])))
        self.assertEqual(track['shape_start']['length_m'],4)
        self.assertTrue(all(abs((b[1]-a[1])/(b[0]-a[0])-1)<1e-8 for a,b in zip(track['points'],track['points'][1:])))
