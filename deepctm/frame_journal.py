"""Bounded handoff of every preview update to rolling history.

SQL triggers also work with already-running collectors. This is an opt-in
local recording feature; it never changes the upstream SDK or sensor settings.
"""
import sqlite3
import time

TABLE = 'rolling_frame_journal'


def install(connection, enabled_until, retention=120):
    if not 10 <= retention <= 300:
        raise ValueError('Journal retention must be 10–300 seconds')
    with connection:
        connection.execute('CREATE TABLE IF NOT EXISTS rolling_journal_config (id INTEGER PRIMARY KEY CHECK(id=1), enabled_until REAL NOT NULL, retention REAL NOT NULL)')
        connection.execute('INSERT OR REPLACE INTO rolling_journal_config VALUES(1,?,?)', (enabled_until, retention))
        connection.execute(f'''CREATE TABLE IF NOT EXISTS {TABLE} (
            sequence INTEGER PRIMARY KEY AUTOINCREMENT, site TEXT, session TEXT,
            event_key TEXT UNIQUE, received_at REAL, payload TEXT)''')
        connection.execute(f'CREATE INDEX IF NOT EXISTS rolling_journal_receipt ON {TABLE}(received_at)')
        for operation in ('INSERT', 'UPDATE'):
            connection.execute(f'''CREATE TRIGGER IF NOT EXISTS rolling_journal_{operation.lower()}
                AFTER {operation} ON preview_frames BEGIN
                DELETE FROM {TABLE} WHERE received_at < CAST(strftime('%s','now') AS REAL)
                    - (SELECT retention FROM rolling_journal_config WHERE id=1);
                INSERT OR IGNORE INTO {TABLE}(site,session,event_key,received_at,payload)
                    SELECT NEW.site,NEW.session,NEW.event_key,NEW.received_at,NEW.payload
                    WHERE NOT EXISTS (SELECT 1 FROM {TABLE} WHERE event_key=NEW.event_key)
                    AND CAST(strftime('%s','now') AS REAL) < (SELECT enabled_until FROM rolling_journal_config WHERE id=1)
                    AND NEW.received_at >= CAST(strftime('%s','now') AS REAL)
                        - (SELECT retention FROM rolling_journal_config WHERE id=1);
                END''')


def read_batch(connection, after=0, limit=2000):
    return connection.execute(f'SELECT sequence,site,session,event_key,received_at,payload FROM {TABLE} WHERE sequence>? ORDER BY sequence LIMIT ?', (after,limit)).fetchall()


def copy_batch(source, destination, ids, after, now=None):
    now=time.time() if now is None else now
    rows=read_batch(source,after)
    with destination:
        for seq,site,session,key,receipt,payload in rows:
            if site in ids and now-5400 <= receipt <= now+1:
                destination.execute('INSERT OR IGNORE INTO frames VALUES(?,?,?,?,?)',(site,session,key,receipt,payload))
    return rows[-1][0] if rows else after, len(rows)
