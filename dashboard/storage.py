"""SQLite persistence. Raw site data stays in ignored data/, never in Git."""
import json
import sqlite3
from pathlib import Path

class Store:
    def __init__(self, path='data/ouster.sqlite3'):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
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
            ''')

    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def save_windows(self, windows):
        with self.connect() as db:
            for w, result in windows:
                db.execute('INSERT OR REPLACE INTO windows VALUES (?,?,?,?,?,?,?)',
                    (w['site'],w['approach'],w['start'],w['end'],w['source'],json.dumps(w),json.dumps(result)))

    def history(self, site=None, start=None, end=None, source=None, approach=None):
        sql, args = 'SELECT * FROM windows WHERE 1=1', []
        for expression, value in [('site=?',site), ('start>=?',start), ('end<=?',end), ('source=?',source), ('approach=?',approach)]:
            if value is not None:
                sql += ' AND '+expression; args.append(value)
        with self.connect() as db:
            rows = db.execute(sql+' ORDER BY start LIMIT 10000',args).fetchall()
        return [dict(site=r['site'],approach=r['approach'],start=r['start'],end=r['end'],source=r['source'],**json.loads(r['result'])) for r in rows]

    def save_event(self, site, timestamp, event):
        with self.connect() as db:
            db.execute('INSERT OR IGNORE INTO events VALUES (?,?,?)',(site,timestamp,json.dumps(event)))
            if 'frame' in event:
                db.execute('INSERT OR REPLACE INTO frames VALUES (?,?,?)',(site,timestamp,json.dumps(event['frame'])))

    def latest(self, site):
        with self.connect() as db:
            row = db.execute('SELECT time,payload FROM frames WHERE site=? ORDER BY time DESC LIMIT 1',(site,)).fetchone()
        return {'timestamp':row['time'],'frame':json.loads(row['payload'])} if row else None
