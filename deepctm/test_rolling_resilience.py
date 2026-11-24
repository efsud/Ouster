import json
import sqlite3
import tempfile
import unittest
from concurrent.futures import Future
from pathlib import Path

from .florida_rolling import connect, database_busy, figure_due, finish_figure, REFRESH


class RollingResilienceTests(unittest.TestCase):
    def test_wal_reader_and_ingester_do_not_block_each_other(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'buffer.sqlite3';writer=connect(path)
            self.assertEqual(writer.execute('PRAGMA journal_mode').fetchone()[0],'wal')
            writer.execute('INSERT INTO frames VALUES(?,?,?,?,?)',('site','s','a',100.,'{}'));writer.commit()
            reader=sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=.05)
            reader.execute('BEGIN')
            self.assertEqual(reader.execute('SELECT count(*) FROM frames').fetchone()[0],1)
            writer.execute('PRAGMA busy_timeout=50')
            writer.execute('INSERT INTO frames VALUES(?,?,?,?,?)',('site','s','b',101.,'{}'));writer.commit()
            # Existing read view stays consistent; the writer nevertheless commits.
            self.assertEqual(reader.execute('SELECT count(*) FROM frames').fetchone()[0],1)
            reader.commit()
            self.assertEqual(reader.execute('SELECT count(*) FROM frames').fetchone()[0],2)
            # In-progress writes cannot starve a new figure read.
            writer.execute('INSERT INTO frames VALUES(?,?,?,?,?)',('site','s','c',102.,'{}'))
            self.assertEqual(reader.execute('SELECT count(*) FROM frames').fetchone()[0],2)
            writer.rollback();reader.close();writer.close()

    def test_requested_refresh_cannot_count_startup_purge_as_collection(self):
        # Purge finished at1000 aftera long process startup; only10sof collection.
        self.assertFalse(figure_due(1010,1000,0,True,None,0,980,1010))
        self.assertTrue(figure_due(1031,1000,0,True,None,0,1000,1031))

    def test_warm_process_without_useful_or_fresh_receipts_cannot_publish(self):
        for bounds in ((None,None),(200,205),(100,140)):
            self.assertFalse(figure_due(205,100,0,True,None,0,*bounds))
        self.assertTrue(figure_due(205,100,0,False,None,0,170,205))

    def test_inflight_job_and_retry_backoff_prevent_duplicate_work(self):
        self.assertFalse(figure_due(205,100,0,True,Future(),0,170,205))
        self.assertFalse(figure_due(205,100,190,True,None,210,170,205))
        self.assertTrue(figure_due(211,100,190,False,None,210,170,211))
        self.assertFalse(figure_due(205,100,190,False,None,0,170,205))

    def test_locked_async_build_keeps_last_snapshot_and_then_recovers(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);(folder/'snapshot.json').write_text('{"old":true}')
            failed=Future();failed.set_exception(sqlite3.OperationalError('database is locked'))
            state=finish_figure(failed,folder,200)
            self.assertEqual(state['figure_state'],'retrying')
            self.assertEqual(state['figure_error'],'database_busy')
            self.assertEqual(state['figure_retry_at'],205)
            self.assertEqual(json.loads((folder/'snapshot.json').read_text()),{'old':True})
            success=Future();success.set_result({'start':180,'end':210,'sites':[]})
            restored=finish_figure(success,folder,210,state['figure_failures'])
            self.assertEqual(restored['figure_state'],'ready')
            self.assertEqual(restored['figure_failures'],0)
            self.assertEqual(json.loads((folder/'snapshot.json').read_text())['end'],210)

    def test_async_failure_retry_is_bounded_and_error_text_not_exposed(self):
        with tempfile.TemporaryDirectory() as tmp:
            future=Future();future.set_exception(ValueError('payload contents should not be exposed'))
            result=finish_figure(future,Path(tmp),100,3)
            self.assertEqual(result['figure_state'],'failed_waiting_retry')
            self.assertEqual(result['figure_retry_at'],100+REFRESH)
            self.assertEqual(result['figure_error'],'ValueError')
            self.assertNotIn('payload',json.dumps(result))

    def test_busy_detection_does_not_hide_other_storage_or_query_errors(self):
        self.assertTrue(database_busy(sqlite3.OperationalError('database is locked')))
        self.assertFalse(database_busy(sqlite3.OperationalError('disk I/O error')))
        self.assertFalse(database_busy(sqlite3.OperationalError('no such table: frames')))
        self.assertFalse(database_busy(ValueError('database is locked')))

    def test_nonfinite_result_does_not_overwrite_complete_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);(folder/'snapshot.json').write_text('{"good":true}')
            future=Future();future.set_result({'speed':float('nan')})
            state=finish_figure(future,folder,100)
            self.assertEqual(state['figure_error'],'ValueError')
            self.assertEqual(json.loads((folder/'snapshot.json').read_text()),{'good':True})


if __name__=='__main__':unittest.main()
