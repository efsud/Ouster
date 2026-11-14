import gc
import sqlite3
import tempfile
import unittest
from pathlib import Path
from dashboard.storage import Store

class ConnectionLifecycleTest(unittest.TestCase):
    def test_repeated_reads_close_without_garbage_collection(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(Path(tmp)/'db');enabled=gc.isenabled();gc.disable()
            try:
                for i in range(1000):
                    with store.connect() as db:db.execute('SELECT 1').fetchone()
                    with self.assertRaises(sqlite3.ProgrammingError):db.execute('SELECT 1')
            finally:
                if enabled:gc.enable()
    def test_commit_rollback_and_close(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(Path(tmp)/'db')
            with store.connect() as db:db.execute('CREATE TABLE lifecycle(value)')
            with store.connect() as db:db.execute('INSERT INTO lifecycle VALUES(1)')
            with self.assertRaises(RuntimeError):
                with store.connect() as failed:
                    failed.execute('INSERT INTO lifecycle VALUES(2)');raise RuntimeError('rollback')
            with self.assertRaises(sqlite3.ProgrammingError):failed.execute('SELECT 1')
            with store.connect() as db:self.assertEqual([r[0] for r in db.execute('SELECT value FROM lifecycle')],[1])
