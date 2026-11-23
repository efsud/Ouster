import sqlite3,time,unittest
from .frame_journal import install,read_batch,copy_batch

class JournalTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:')
        self.db.execute('CREATE TABLE preview_frames(site TEXT PRIMARY KEY,received_at REAL,session TEXT,event_key TEXT,payload TEXT)')
        install(self.db,time.time()+60)
    def tearDown(self):self.db.close()
    def update(self,key,stamp=None):
        self.db.execute('INSERT INTO preview_frames VALUES(?,?,?,?,?) ON CONFLICT(site) DO UPDATE SET received_at=excluded.received_at,event_key=excluded.event_key,payload=excluded.payload',('site',time.time() if stamp is None else stamp,'session',key,'{}'))
    def test_preserves_burst_overwritten_in_preview(self):
        for n in range(50):self.update(str(n))
        self.assertEqual(len(read_batch(self.db)),50)
        self.assertEqual(self.db.execute('select count(*) from preview_frames').fetchone()[0],1)
    def test_duplicate_replay_idempotent(self):
        self.update('same');self.update('same')
        self.assertEqual(len(read_batch(self.db)),1)
    def test_expiry_and_deadline(self):
        self.update('fresh')
        self.db.execute('update rolling_frame_journal set received_at=?',(time.time()-301,))
        install(self.db,time.time()-2)
        self.update('disabled')
        self.assertEqual(read_batch(self.db),[])
    def test_copy_restart_idempotent(self):
        self.update('one');self.update('two')
        target=sqlite3.connect(':memory:')
        target.execute('CREATE TABLE frames(site,session,event_key,received,payload,PRIMARY KEY(site,session,event_key))')
        cursor,n=copy_batch(self.db,target,{'site'},0)
        self.assertEqual(n,2)
        copy_batch(self.db,target,{'site'},0)
        self.assertEqual(target.execute('select count(*) from frames').fetchone()[0],2)
        self.assertEqual(copy_batch(self.db,target,{'site'},cursor)[1],0)
        target.close()

if __name__=='__main__':unittest.main()
