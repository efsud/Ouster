"""SQLite persistence. Raw site data stays in ignored data/, never in Git."""
import json
import sqlite3
import time
import hashlib
from pathlib import Path

class Store:
    def __init__(self, path='data/ouster.sqlite3'):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        if Path(path).exists():
            with self.connect() as existing:
                if existing.execute('PRAGMA user_version').fetchone()[0]<2:
                    backup=Path(str(path)+f'.pre-v2-{time.time_ns()}.bak')
                    with sqlite3.connect(backup) as target: existing.backup(target)
        with self.connect() as db:
            db.executescript('''
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS windows (
                  site TEXT, approach TEXT, start REAL, end REAL,
                  source TEXT, input TEXT, result TEXT,
                  PRIMARY KEY(site, approach, start, end, source));
                CREATE TABLE IF NOT EXISTS frames (
                  site TEXT, time REAL, payload TEXT, PRIMARY KEY(site,time));
                CREATE TABLE IF NOT EXISTS events (
                  site TEXT, time REAL, payload TEXT, PRIMARY KEY(site,time,payload));
                CREATE INDEX IF NOT EXISTS frame_time ON frames(time);
                CREATE TABLE IF NOT EXISTS raw_events (
                  sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                  event_key TEXT UNIQUE NOT NULL, site TEXT NOT NULL, session TEXT NOT NULL,
                  sensor_time REAL, received_at REAL NOT NULL, source TEXT NOT NULL,
                  status TEXT NOT NULL, reason TEXT, payload TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS raw_site_time ON raw_events(site,sensor_time);
                CREATE INDEX IF NOT EXISTS raw_receipt ON raw_events(received_at);
                CREATE INDEX IF NOT EXISTS raw_site_receipt ON raw_events(site,received_at,sensor_time,status);
                CREATE TABLE IF NOT EXISTS preview_frames (
                  site TEXT PRIMARY KEY, received_at REAL, session TEXT, event_key TEXT, payload TEXT);
                CREATE TABLE IF NOT EXISTS latest_frames (
                  site TEXT PRIMARY KEY, sensor_time REAL, received_at REAL,
                  session TEXT, event_key TEXT, payload TEXT);
                CREATE TABLE IF NOT EXISTS collector_health (
                  site TEXT PRIMARY KEY, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS anomalies (
                  id TEXT PRIMARY KEY, site TEXT, approach TEXT, category TEXT,
                  rule TEXT, severity TEXT, start REAL, end REAL, state TEXT,
                  evidence TEXT, acknowledged_at REAL, note TEXT DEFAULT '');
                CREATE INDEX IF NOT EXISTS anomaly_site ON anomalies(site,start);
                CREATE TABLE IF NOT EXISTS evaluations (
                  site TEXT, approach TEXT, start REAL, metric TEXT, status TEXT, evidence TEXT,
                  PRIMARY KEY(site,approach,start,metric));
                CREATE TABLE IF NOT EXISTS latency_samples (
                  event_key TEXT PRIMARY KEY,site TEXT,received_at REAL,sensor_time REAL,displayed_at REAL);
            ''')
            if db.execute('PRAGMA user_version').fetchone()[0]<2:
                # Legacy rows have no receipt clock. Migration time is explicitly recorded.
                now=time.time()
                for r in db.execute('SELECT site,time,payload FROM events').fetchall():
                    event=json.loads(r['payload'])
                    key=self.event_key(r['site'],'legacy',event)
                    db.execute('INSERT OR IGNORE INTO raw_events(event_key,site,session,sensor_time,received_at,source,status,reason,payload) VALUES(?,?,?,?,?,?,?,?,?)',
                        (key,r['site'],'legacy',r['time'],now,'legacy','legacy','Receipt time assigned during migration',r['payload']))
                db.execute('PRAGMA user_version=2')

    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def save_windows(self, windows):
        with self.connect() as db:
            for w, result in windows:
                db.execute('INSERT OR REPLACE INTO windows VALUES (?,?,?,?,?,?,?)',
                    (w['site'],w['approach'],w['start'],w['end'],w['source'],json.dumps(w),json.dumps(result)))

    def history(self, site=None, start=None, end=None, source=None, approach=None, limit=10000, offset=0, cadence=None):
        sql, args = 'SELECT * FROM windows WHERE 1=1', []
        for expression, value in [('site=?',site), ('start>=?',start), ('end<=?',end), ('source=?',source), ('approach=?',approach)]:
            if value is not None:
                sql += ' AND '+expression; args.append(value)
        if cadence=='five_minute':sql+=' AND end-start=300'
        elif cadence=='daily':sql+=' AND end-start BETWEEN 82800 AND 90000'
        with self.connect() as db:
            rows = db.execute(sql+' ORDER BY start,site,approach,source LIMIT ? OFFSET ?',args+[limit,offset]).fetchall()
        return [dict(site=r['site'],approach=r['approach'],start=r['start'],end=r['end'],source=r['source'],**json.loads(r['result'])) for r in rows]

    def save_event(self, site, timestamp, event):
        return self.save_batch([{'site':site,'sensor_time':timestamp,'event':event,'session':'compat','received_at':time.time()}])

    def latest(self, site):
        with self.connect() as db:
            row=db.execute('SELECT * FROM latest_frames WHERE site=?',(site,)).fetchone()
            if row:
                return {'timestamp':row['sensor_time'],'received_at':row['received_at'],'session':row['session'],'event_key':row['event_key'],'frame':json.loads(row['payload'])}
            row = db.execute('SELECT time,payload FROM frames WHERE site=? ORDER BY time DESC LIMIT 1',(site,)).fetchone()
        return {'timestamp':row['time'],'frame':json.loads(row['payload'])} if row else None

    @staticmethod
    def event_key(site, session, event):
        # Session is provenance, not part of dedup key: replay after reconnect is idempotent.
        return hashlib.sha256((site+'\n'+json.dumps(event,sort_keys=True,separators=(',',':'))).encode()).hexdigest()

    def save_batch(self, records):
        inserted=0
        with self.connect() as db:
            for r in records:
                payload=json.dumps(r['event'],sort_keys=True,separators=(',',':'))
                stamp=r.get('sensor_time')
                key=self.event_key(r['site'],r['session'],dict(r['event'],_clock_key=stamp if stamp is not None else r['received_at']))
                status=r.get('status','received')
                result=db.execute('INSERT OR IGNORE INTO raw_events(event_key,site,session,sensor_time,received_at,source,status,reason,payload) VALUES(?,?,?,?,?,?,?,?,?)',
                    (key,r['site'],r['session'],r.get('sensor_time'),r['received_at'],r.get('source','sdk'),status,r.get('reason'),payload))
                inserted+=result.rowcount
                if result.rowcount and 'frame' in r['event'] and (status=='received' or r.get('reason')=='unknown_timezone'):
                    db.execute('INSERT INTO preview_frames VALUES(?,?,?,?,?) ON CONFLICT(site) DO UPDATE SET received_at=excluded.received_at,session=excluded.session,event_key=excluded.event_key,payload=excluded.payload WHERE excluded.received_at>=preview_frames.received_at',
                        (r['site'],r['received_at'],r['session'],key,payload))
                if result.rowcount and 'frame' in r['event'] and r.get('sensor_time') is not None and status=='received':
                    db.execute('''INSERT INTO latest_frames VALUES(?,?,?,?,?,?) ON CONFLICT(site) DO UPDATE SET
                        sensor_time=excluded.sensor_time,received_at=excluded.received_at,session=excluded.session,
                        event_key=excluded.event_key,payload=excluded.payload WHERE excluded.sensor_time>=latest_frames.sensor_time''',
                        (r['site'],r['sensor_time'],r['received_at'],r['session'],key,json.dumps(r['event']['frame'])))
        return inserted

    def save_preview(self, records):
        """Replace only the latest display frame; do not append raw history."""
        with self.connect() as db:
            for r in records:
                if 'frame' not in r['event'] or not (r['status']=='received' or r.get('reason')=='unknown_timezone'):continue
                key=self.event_key(r['site'],r['session'],dict(r['event'],_clock_key=r.get('sensor_time') or r['received_at']))
                db.execute('INSERT INTO preview_frames VALUES(?,?,?,?,?) ON CONFLICT(site) DO UPDATE SET received_at=excluded.received_at,session=excluded.session,event_key=excluded.event_key,payload=excluded.payload WHERE excluded.received_at>=preview_frames.received_at',
                    (r['site'],r['received_at'],r['session'],key,json.dumps(r['event'])))
                if r['status']=='received' and r.get('sensor_time') is not None:
                    db.execute('INSERT INTO latest_frames VALUES(?,?,?,?,?,?) ON CONFLICT(site) DO UPDATE SET sensor_time=excluded.sensor_time,received_at=excluded.received_at,session=excluded.session,event_key=excluded.event_key,payload=excluded.payload WHERE excluded.sensor_time>=latest_frames.sensor_time',
                        (r['site'],r['sensor_time'],r['received_at'],r['session'],key,json.dumps(r['event']['frame'])))

    def set_health(self, site, **fields):
        with self.connect() as db:
            row=db.execute('SELECT payload FROM collector_health WHERE site=?',(site,)).fetchone()
            value=json.loads(row[0]) if row else {}
            value.update(fields,updated_at=time.time(),site=site)
            db.execute('INSERT OR REPLACE INTO collector_health VALUES(?,?)',(site,json.dumps(value)))

    def health(self, site):
        with self.connect() as db:
            row=db.execute('SELECT payload FROM collector_health WHERE site=?',(site,)).fetchone()
        return json.loads(row[0]) if row else {'site':site,'state':'not_started'}

    def raw_page(self, site=None, start=None, end=None, after=0, limit=100):
        sql='SELECT * FROM raw_events WHERE sequence>?';args=[after]
        for exp,val in [('site=?',site),('sensor_time>=?',start),('sensor_time<?',end)]:
            if val is not None:sql+=' AND '+exp;args.append(val)
        with self.connect() as db:
            rows=db.execute(sql+' ORDER BY sequence LIMIT ?',args+[limit+1]).fetchall()
        data=[{**dict(r),'payload':json.loads(r['payload'])} for r in rows[:limit]]
        return {'items':data,'next_cursor':data[-1]['sequence'] if len(rows)>limit else None}

    def availability(self,site):
        with self.connect() as db:
            r=db.execute('SELECT count(*) count,min(sensor_time) first,max(sensor_time) last,min(received_at) first_receipt,max(received_at) last_receipt FROM raw_events WHERE site=?',(site,)).fetchone()
            kinds=db.execute('SELECT status,count(*) count FROM raw_events WHERE site=? GROUP BY status',(site,)).fetchall()
        return dict(r,status_counts={x['status']:x['count'] for x in kinds},retention_days=30)

    def recorded_summary(self,site):
        """Last recorded hour, by receipt clock; event counts are not vehicle counts."""
        with self.connect() as db:
            bounds=db.execute('SELECT min(received_at) first,max(received_at) last FROM raw_events INDEXED BY raw_site_receipt WHERE site=?',(site,)).fetchone()
            if bounds['last'] is None:return {'site':site,'events':0,'buckets':[],'basis':'receipt time'}
            end=bounds['last'];start=max(bounds['first'],end-3600)
            rows=db.execute('SELECT CAST((received_at-?)/60 AS INTEGER) minute,count(*) count FROM raw_events INDEXED BY raw_site_receipt WHERE site=? AND received_at>=? AND received_at<=? GROUP BY minute ORDER BY minute',(start,site,start,end)).fetchall()
            counts={r['minute']:r['count'] for r in rows}
            quality=db.execute('SELECT status,count(*) count FROM raw_events INDEXED BY raw_site_receipt WHERE site=? AND received_at>=? AND received_at<=? GROUP BY status',(site,start,end)).fetchall()
        return {'site':site,'start':start,'end':end,'events':sum(counts.values()),'basis':'receipt time','status_counts':{r['status']:r['count'] for r in quality},'buckets':[{'start':start+i*60,'events':counts.get(i,0)} for i in range(int((end-start)//60)+1)]}

    def purge_raw(self, now=None):
        cutoff=(time.time() if now is None else now)-30*86400
        with self.connect() as db:
            db.execute("DELETE FROM events WHERE EXISTS(SELECT 1 FROM raw_events r WHERE r.source='legacy' AND r.site=events.site AND r.sensor_time=events.time AND r.received_at<?)",(cutoff,))
            db.execute("DELETE FROM frames WHERE EXISTS(SELECT 1 FROM raw_events r WHERE r.source='legacy' AND r.site=frames.site AND r.sensor_time=frames.time AND r.received_at<?)",(cutoff,))
            count=db.execute('DELETE FROM raw_events WHERE received_at<?',(cutoff,)).rowcount
            db.execute('DELETE FROM latest_frames WHERE received_at<?',(cutoff,))
            db.execute('DELETE FROM preview_frames WHERE received_at<?',(cutoff,))
        for backup in Path(self.path).parent.glob(Path(self.path).name+'.pre-v2-*.bak'):
            if backup.stat().st_mtime<cutoff:backup.unlink()
        return count

    def record_latency(self,event_key,displayed_at):
        with self.connect() as db:
            r=db.execute('SELECT site,sensor_time,received_at FROM raw_events WHERE event_key=?',(event_key,)).fetchone()
            if not r:return False
            if not r['received_at']<=displayed_at<=time.time()+5:raise ValueError('Invalid display clock')
            db.execute('INSERT OR IGNORE INTO latency_samples VALUES(?,?,?,?,?)',(event_key,r['site'],r['received_at'],r['sensor_time'],displayed_at))
        return True

    def window_input(self,site,approach,start,end,source):
        with self.connect() as db:
            r=db.execute('SELECT input,result FROM windows WHERE site=? AND approach=? AND start=? AND end=? AND source=?',(site,approach,start,end,source)).fetchone()
        return {'input':json.loads(r['input']),'result':json.loads(r['result'])} if r else None

    def save_anomaly(self,a):
        with self.connect() as db:
            db.execute('''INSERT INTO anomalies(id,site,approach,category,rule,severity,start,end,state,evidence)
              VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET end=excluded.end,state=excluded.state,evidence=excluded.evidence''',
              (a['id'],a['site'],a.get('approach',''),a['category'],a['rule'],a.get('severity','warning'),a['start'],a.get('end',a['start']),a.get('state','active'),json.dumps(a['evidence'])))

    def anomaly_page(self,site=None,category=None,offset=0,limit=100):
        sql='SELECT * FROM anomalies WHERE 1=1';args=[]
        for exp,val in [('site=?',site),('category=?',category)]:
            if val:sql+=' AND '+exp;args.append(val)
        with self.connect() as db:rows=db.execute(sql+' ORDER BY start DESC,id LIMIT ? OFFSET ?',args+[limit+1,offset]).fetchall()
        return {'items':[{**dict(r),'evidence':json.loads(r['evidence'])} for r in rows[:limit]],'next_offset':offset+limit if len(rows)>limit else None}

    def acknowledge(self,identifier,note):
        with self.connect() as db:
            return db.execute('UPDATE anomalies SET acknowledged_at=?,note=? WHERE id=?',(time.time(),note,identifier)).rowcount>0
