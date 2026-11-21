import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch
from .corridor import configuration,geometry
from .capture import retry_site

class CorridorTest(unittest.TestCase):
    def test_ten_sites_order_and_positive_stationing(self):
        c=configuration(json.loads(Path('config/sites.json').read_text())['sites'])
        self.assertEqual(len(c['sites_west_to_east']),10)
        self.assertEqual(len(set(c['sites_west_to_east'])),10)
        self.assertEqual(c['site_names'][0],'Martin Grove');self.assertEqual(c['site_names'][-1],'Driftwood')
        self.assertTrue(all(b>a for a,b in zip(c['station_m'],c['station_m'][1:])))
        self.assertEqual(len(c['road_bearings_deg']),10)
    def test_exhausted_site_does_not_stop_healthy_peer(self):
        peers={'failed':Mock(),'healthy':Mock()};manifest={'restarts':{'failed':10},'unavailable_sites':[]};launch=Mock()
        with tempfile.TemporaryDirectory() as tmp,patch('deepctm.capture.stop') as stop:
            retry_site('failed',peers,manifest,Path(tmp),launch)
            stop.assert_called_once_with(peers['failed']);launch.assert_not_called()
            self.assertEqual(json.loads((Path(tmp)/'manifest.json').read_text())['unavailable_sites'],['failed'])
        self.assertIn('healthy',peers)
    def test_retry_keeps_deadline_and_relaunches_only_failed(self):
        manifest={'end':1000,'restarts':{},'unavailable_sites':[]};launch=Mock()
        with tempfile.TemporaryDirectory() as tmp,patch('deepctm.capture.stop'):
            retry_site('a',{'a':Mock()},manifest,Path(tmp),launch)
            self.assertEqual(manifest['end'],1000);self.assertEqual(manifest['restarts']['a'],1);launch.assert_called_once_with('a')

    def test_damaged_archive_preserves_readable_rows_and_reports_issue(self):
        import gzip
        from .figures import recorded_events
        with tempfile.TemporaryDirectory() as tmp:
            row={'received_at':1,'session':'s','payload':{'frame':{}}}
            content=gzip.compress((json.dumps(row)+'\n').encode())
            (Path(tmp)/'site-1.jsonl.gz').write_bytes(content[:-8])
            issues=[];rows=list(recorded_events(tmp,'site',issues))
            self.assertEqual(len(rows),1);self.assertEqual(len(issues),1)
    def test_ten_site_plot_with_missing_site(self):
        import numpy as np
        from .figures import draw
        tracks=[[]]+[[{'direction':'eastbound','points':np.array([[0.,-10.,2.],[1.,-8.,2.],[2.,-6.,2.]])}] for _ in range(9)]
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp)/'test.png'
            count=draw(tracks,'eastbound',0,300,list(range(0,5000,500)),output,'Software test only',[str(i) for i in range(10)])
            self.assertEqual(count,9);self.assertTrue(output.read_bytes().startswith(b'\x89PNG'))
