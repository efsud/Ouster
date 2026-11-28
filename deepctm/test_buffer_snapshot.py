import sqlite3,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from .buffer_snapshot import copy_buffer

class BufferSnapshotTests(unittest.TestCase):
    def test_concurrent_writes_do_not_restart_or_change_pinned_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'live.sqlite3';writer=sqlite3.connect(path)
            writer.execute('PRAGMA journal_mode=WAL');writer.execute('CREATE TABLE events(id INTEGER PRIMARY KEY,payload BLOB)')
            writer.executemany('INSERT INTO events(payload) VALUES (?)',[(b'x'*4096,)]*500);writer.commit()
            writes=[]
            def during_copy(status,remaining,total):
                if not writes:
                    writer.execute('INSERT INTO events(payload) VALUES (?)',(b'new',));writer.commit();writes.append(True)
            copied=copy_buffer(path,progress_hook=during_copy)
            self.assertEqual(copied.execute('SELECT count(*) FROM events').fetchone()[0],500)
            self.assertEqual(writer.execute('SELECT count(*) FROM events').fetchone()[0],501)
            copied.close();writer.close()
    def test_deadline_aborts_without_altering_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'live.sqlite3';db=sqlite3.connect(path);db.execute('CREATE TABLE events(id)');db.commit();db.close()
            with patch('deepctm.buffer_snapshot.time.monotonic',side_effect=[0,2]):
                with self.assertRaises(TimeoutError):copy_buffer(path,max_seconds=1)
            db=sqlite3.connect(path);db.execute('INSERT INTO events VALUES (1)');db.commit();self.assertEqual(db.execute('SELECT count(*) FROM events').fetchone()[0],1);db.close()
