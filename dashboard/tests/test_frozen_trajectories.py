import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from dashboard.frozen_trajectories import read


class FrozenTrajectoryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.capture='20261124T194525Z'
        self.path=self.root/self.capture;self.path.mkdir()
        self.manifest={'state':'frozen','created_at':99999,'start':0,'end':3600,'checksums':{}}
        self.write('snapshot.json',{'start':0,'end':3600,'generated_at':3600,'sites':[]})
        self.write('reconstruction.json',{'start':0,'end':3600,'snapshot_generated_at':3600,'expires_at':5400})

    def write(self,name,data):
        raw=json.dumps(data).encode();(self.path/name).write_bytes(raw)
        self.manifest['checksums'][name]=hashlib.sha256(raw).hexdigest()
        (self.path/'manifest.json').write_text(json.dumps(self.manifest))

    def test_fixed_hour_survives_rolling_expiry_without_future_refresh(self):
        result=read(self.capture,folder=self.root)
        self.assertEqual(result['state'],'ready');self.assertTrue(result['frozen'])
        self.assertEqual((result['start'],result['end']),(0,3600))
        self.assertIsNone(result['next_update']);self.assertIsNone(result['expires_at'])
        result=read(self.capture,True,self.root)
        self.assertEqual(result['state'],'ready');self.assertIsNone(result['expires_at'])

    def test_pending_and_missing_capture_do_not_publish_partial_data(self):
        self.manifest['state']='verifying';self.write('snapshot.json',{'start':0,'end':3600})
        self.assertEqual(read(self.capture,folder=self.root)['state'],'waiting')
        self.assertEqual(read('20260101T000000Z',folder=self.root)['state'],'unavailable')

    def test_rejects_traversal_and_symlinked_assets(self):
        for name in ('../private','20261124T194525Z/../../private',None):
            with self.assertRaises(ValueError):read(name,folder=self.root)
        (self.path/'snapshot.json').unlink();outside=self.root/'private.json';outside.write_text('{}')
        (self.path/'snapshot.json').symlink_to(outside)
        with self.assertRaises(ValueError):read(self.capture,folder=self.root)

    def test_changed_data_and_mismatched_reconstruction_are_rejected(self):
        (self.path/'snapshot.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'integrity'):read(self.capture,folder=self.root)
        self.write('reconstruction.json',{'start':0,'end':3600,'snapshot_generated_at':7200})
        with self.assertRaisesRegex(ValueError,'window'):read(self.capture,True,self.root)


if __name__=='__main__':unittest.main()
