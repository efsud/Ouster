import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from deepctm import finch_rolling

class FinchRollingTest(unittest.TestCase):
    def test_finch_reads_only_its_own_snapshot_and_expires(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            with patch.object(finch_rolling, 'FOLDER', folder):
                self.assertEqual(finch_rolling.read_snapshot(6400)['state'], 'warming')
                (folder / 'snapshot.json').write_text(json.dumps({'start':1000,'sites':[{'id':'finch'}],'estimates':{'links':[{'paths':['old inter-site path']}]}}))
                result = finch_rolling.read_snapshot(6400)
                self.assertEqual(result['sites'][0]['id'], 'finch')
                self.assertEqual(result['state'], 'ready')
                self.assertEqual(result['estimates']['links'], [])
                self.assertEqual(finch_rolling.read_snapshot(6401)['state'], 'expired')
