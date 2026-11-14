import copy
import json
import tempfile
import time
import sqlite3
import unittest
from pathlib import Path
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
from dashboard.storage import Store
from dashboard.reception import normalize_event
from dashboard.calibration import report
from dashboard.processing import build_window,calendar_bounds,process_range
from dashboard.anomalies import baseline,evaluate_traffic,evaluate_health


def site_fixture():
    return {'id':'TEST','timezone':'America/Toronto','origin':{'lat':43,'lng':-79},'rotation_deg':0,'calibration_verified':True,
        'calibration':{'version':'fixture-1','reference':'Synthetic independent control points','landmarks':[{'x':0,'y':0,'lat':43,'lng':-79},{'x':10,'y':0,'lat':43,'lng':-78.99987716},{'x':0,'y':10,'lat':43.00008983,'lng':-79}]},
        'scene':{'verified':True,'version':'scene-fixture-1','reference':'Synthetic lane','signal_synchronized':False,'approaches':[{'id':'EB','centerline':[[0,0],[100,0]],'analysis_polygon':[[-30,-4],[140,-4],[140,4],[-30,4]],'queue_polygon':[[0,-4],[100,-4],[100,4],[0,4]],'free_speed_mps':10,'lanes':1,'visibility_verified':True,'exit_offset_m':3,'storage_m':100,'storage_verified':True}]}}


def frames(start=0,end=300):
    rows=[]
    for t in range(start,end+1):
        objects=[]
        for n in range(20):
            enter=10+n*12;x=(t-enter)*10
            if -20<=x<=120:objects.append({'id':str(n),'classType':'2','centerX':x,'centerY':0})
        rows.append({'sequence':t+1,'site':'TEST','session':'session-1','sensor_time':t,'received_at':t+.1,'status':'received','event_key':str(t),'payload':{'timestamp':datetime.fromtimestamp(t,ZoneInfo('UTC')).isoformat(),'frame':{'objects':objects}}})
    return rows

class ReceptionTest(unittest.TestCase):
    def test_timezone_is_not_guessed(self):
        for stamp,reason in [('2026-09-23T12:00:00','unknown_timezone'),('broken','invalid_timestamp'),('', 'missing_timestamp')]:
            r=normalize_event('S','session',{'timestamp':stamp},2e9)
            self.assertEqual(r['status'],'quarantined');self.assertEqual(r['reason'],reason)
    def test_utc_and_future(self):
        r=normalize_event('S','x',{'timestamp':'1970-01-01T00:01:40Z'},101)
        self.assertEqual(r['sensor_time'],100);self.assertEqual(r['status'],'received')
        self.assertEqual(normalize_event('S','x',{'timestamp':'1970-01-01T00:01:50Z'},100)['reason'],'future_timestamp')

class DurableStoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'db';self.store=Store(self.path)
    def tearDown(self):self.tmp.cleanup()
    def record(self,t=100,received=100,session='a'):
        return dict(site='TEST',session=session,sensor_time=t,received_at=received,status='received',event={'timestamp':str(t),'frame':{'objects':[]}})
    def test_batch_restart_dedup_and_order(self):
        self.assertEqual(self.store.save_batch([self.record(100),self.record(90)]),2)
        self.assertEqual(self.store.save_batch([self.record(100,session='new')]),0)
        other=Store(self.path);self.assertEqual(other.latest('TEST')['timestamp'],100)
        first=other.raw_page(limit=1);self.assertIsNotNone(first['next_cursor'])
        second=other.raw_page(after=first['next_cursor'],limit=1);self.assertIsNone(second['next_cursor'])
        self.assertNotEqual(first['items'][0]['event_key'],second['items'][0]['event_key'])
    def test_failed_batch_is_atomic(self):
        with self.assertRaises(KeyError):self.store.save_batch([self.record(),{'site':'bad'}])
        self.assertEqual(self.store.availability('TEST')['count'],0)
    def test_retention_uses_receipt_not_sensor_clock(self):
        now=3e6;cutoff=now-30*86400
        self.store.save_batch([self.record(1,cutoff-1),self.record(2,cutoff),self.record(3,now)])
        self.assertEqual(self.store.purge_raw(now),1)
        self.assertEqual(self.store.availability('TEST')['count'],2)
    def test_migration_backup_before_change(self):
        legacy=Path(self.tmp.name)/'legacy'
        with sqlite3.connect(legacy) as c:c.execute('CREATE TABLE marker(value)');c.execute('INSERT INTO marker VALUES(42)')
        Store(legacy)
        backups=list(Path(self.tmp.name).glob('legacy.pre-v2-*.bak'));self.assertEqual(len(backups),1)
        with sqlite3.connect(backups[0]) as c:
            self.assertEqual(c.execute('SELECT value FROM marker').fetchone()[0],42)
            self.assertEqual(c.execute('PRAGMA user_version').fetchone()[0],0)

class ProcessingTest(unittest.TestCase):
    def test_calibration_residual_and_gate(self):
        s=site_fixture();self.assertTrue(report(s)['valid'])
        s['calibration']['landmarks'][0]['lat']+=.01;self.assertFalse(report(s)['valid'])
        with self.assertRaises(ValueError):build_window(s,frames(),0,300)
    def test_known_motion_conservation_and_counts(self):
        w,r=build_window(site_fixture(),frames(),0,300)[0]
        self.assertEqual(r['quality']['valid_tracks'],20)
        self.assertAlmostEqual(r['values']['control_delay'],0)
        self.assertEqual(r['values']['volume'],240)
        self.assertEqual(r['values']['stopped_delay'],0)
        self.assertIsNone(r['values']['aog'])
        self.assertEqual(w['provenance']['merge_count'],0)
    def test_censor_and_gap_do_not_invent_traversal(self):
        data=frames();data=[r for r in data if not 15<=r['sensor_time']<=20]
        w,r=build_window(site_fixture(),data,0,300)[0]
        self.assertLess(r['quality']['valid_tracks'],20)
        self.assertTrue(all(t['max_gap_s']<=3 for t in w['tracks']))
    def test_sessions_are_namespaced(self):
        data=frames()
        for r in data:
            if r['sensor_time']>=150:r['session']='second'
        w,r=build_window(site_fixture(),data,0,300)[0]
        self.assertTrue(w['provenance']['collector_reset'])
        self.assertIsNone(r['values']['aog'])
        self.assertEqual(len({t['id'] for t in w['tracks']}),len(w['tracks']))
    def test_known_green_arrivals_and_red_transition(self):
        site=site_fixture();site['scene']['signal_synchronized']=True;site['scene']['approaches'][0]['phase']=2
        data=frames()
        for t,status in [(-1,1),(150,3),(300,1)]:
            data.append({'sequence':1000+t,'site':'TEST','session':'session-1','sensor_time':t,'received_at':t+.1,'status':'received','event_key':str(t),'payload':{'phaseChange':{'phases':[{'phaseNumber':2,'status':status}]}}})
        w,r=build_window(site,data,0,300)[0]
        # Arrivals at 20,32,...,248: eleven arrive before the red at 150.
        self.assertEqual(r['values']['aog'],55)
        self.assertEqual(w['green_seconds'],150)
        self.assertEqual(r['values']['discharge'],0)

    def test_dst_calendar_days(self):
        for day,hours in [('2026-03-08',23),('2026-11-01',25),('2026-09-23',24)]:
            a,b=calendar_bounds(day);self.assertEqual(b-a,hours*3600)
    def test_no_frames_no_manufactured_kpi(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError,'No valid'):process_range(Store(Path(tmp)/'db'),site_fixture(),0,300)

class AnomalyTest(unittest.TestCase):
    def row(self,start,value):
        return {'site':'TEST','approach':'EB','start':start,'end':start+300,'source':'sdk-derived','values':{'queue_p95':value},'quality':{'coverage':1,'valid_tracks':20,'visible_queue_samples':300,'flags':[]}}
    def history(self):
        target=datetime(2026,9,23,12,tzinfo=ZoneInfo('America/Toronto'))
        rows=[]
        for i in range(1,30):
            day=target-timedelta(days=i)
            if day.weekday()<5:rows.append(self.row(day.timestamp(),10+i%5))
        return self.row(target.timestamp(),100),rows
    def test_robust_baseline_warmup_and_zero_mad(self):
        current,rows=self.history()
        self.assertEqual(baseline(current,rows,'queue_p95','America/Toronto')['status'],'outlier')
        self.assertEqual(baseline(current,rows[:3],'queue_p95','America/Toronto')['status'],'insufficient_baseline')
        for r in rows:r['values']['queue_p95']=10
        self.assertEqual(baseline(current,rows,'queue_p95','America/Toronto')['status'],'zero_mad')
    def test_persistence_ack_recovery_and_retention(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Store(Path(tmp)/'db');current,rows=self.history()
            second=self.row(current['end'],110);normal=self.row(second['end'],12)
            def save(rows):
                db.save_windows([(dict(r),{'values':r['values'],'quality':r['quality']}) for r in rows])
            save(rows+[current]);evaluate_traffic(db,site_fixture());self.assertEqual(db.anomaly_page()['items'],[])
            save([second]);evaluate_traffic(db,site_fixture())
            alerts=db.anomaly_page()['items'];self.assertGreaterEqual(len(alerts),1)
            identifier=alerts[0]['id'];db.acknowledge(identifier,'Reviewed example');evaluate_traffic(db,site_fixture())
            self.assertEqual(len(db.anomaly_page()['items']),len(alerts))
            self.assertEqual(db.anomaly_page()['items'][0]['note'],'Reviewed example')
            save([normal]);evaluate_traffic(db,site_fixture());self.assertTrue(all(a['state']=='resolved' for a in db.anomaly_page()['items']))
            db.purge_raw(2e9);self.assertEqual(len(db.anomaly_page()['items']),len(alerts))
    def test_outage_is_data_quality_not_zero_traffic(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Store(Path(tmp)/'db');db.set_health('TEST',state='receiving',last_receipt=100)
            evaluate_health(db,site_fixture(),110)
            alerts=db.anomaly_page()['items'];self.assertEqual(alerts[0]['rule'],'stale_stream');self.assertEqual(alerts[0]['category'],'data_quality')
            db.set_health('TEST',last_receipt=111);evaluate_health(db,site_fixture(),111)
            self.assertEqual(db.anomaly_page()['items'][0]['state'],'resolved')

if __name__=='__main__':unittest.main()
