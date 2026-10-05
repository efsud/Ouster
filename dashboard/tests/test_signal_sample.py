import json
from pathlib import Path
import tempfile
import unittest
from scripts.analyze_signal_sample import analyze


class SampleAnalysisTest(unittest.TestCase):
    def test_snapshots_duplicates_gaps_and_censored_episodes(self):
        rows = []
        # Initial snapshot is not a green onset. Repeated reports do not reset onset.
        for receipt,stamp,status,absolute in [(0,0,1,True),(2,2,2,False),
                (5,5,3,False),(8,8,1,False),(9,9,1,False),(18,18,2,False),
                (100,100,3,False),(101,101,1,False),(102,102,2,True)]:
            from datetime import datetime, timedelta
            timestamp=(datetime(2026,1,1)+timedelta(seconds=stamp)).isoformat()
            rows.append(dict(received_at=receipt,event=dict(timestamp=timestamp,
                phaseChange=dict(absolute=absolute,phases=[dict(phaseNumber='2',status=status)]))))
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'raw.jsonl').write_text('\n'.join(map(json.dumps,rows)))
            result=analyze(p)
        green=[e for e in result['episodes'] if e['colour']=='GREEN']
        self.assertEqual([e['sensor_seconds'] for e in green],[10])
        self.assertEqual(len(result['gaps']),1)
        self.assertEqual(result['cycles'],[])
        self.assertFalse(result['movement_mapping_verified'])
