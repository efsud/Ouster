"""Bounded consistent copies of a live WAL buffer for read-only validation."""
import sqlite3,time
from pathlib import Path

def copy_buffer(path,max_seconds=30,progress_hook=None):
    if max_seconds<=0:raise ValueError('Positive copy deadline required')
    source=sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True,timeout=1)
    memory=sqlite3.connect(':memory:');started=time.monotonic()
    def progress(status,remaining,total):
        if time.monotonic()-started>max_seconds:raise TimeoutError('Live buffer snapshot exceeded copy deadline')
        if progress_hook is not None:progress_hook(status,remaining,total)
    try:
        # Pin one consistent read version only during the copy. Without this,
        # frequent external commits can repeatedly restart incremental backup.
        source.execute('BEGIN')
        source.execute('SELECT name FROM sqlite_master LIMIT 1').fetchone()
        source.backup(memory,pages=128,sleep=.01,progress=progress)
        return memory
    except BaseException:
        memory.close();raise
    finally:
        source.close()
