"""The region selector must read the matching collector database."""
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from dashboard.server import Handler, live_store
from dashboard.storage import Store

class CombinedLiveTest(unittest.TestCase):
    def test_network_switch_uses_separate_streams_and_keeps_history_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            history=Store(Path(tmp)/'history')
            stores={region:Store(Path(tmp)/region) for region in ['Toronto','Florida']}
            sites=[]
            for region,store in stores.items():
                site={'id':region,'region':region,'reference_location':{'lat':43 if region=='Toronto' else 28,'lng':-79},'preview_rotation_deg':90}
                sites.append(site)
                store.save_preview([dict(site=region,session='test',received_at=time.time(),sensor_time=None,status='quarantined',reason='unknown_timezone',event={'frame':{'objects':[{'id':region+'-car','centerX':10}]}})])
            server=SimpleNamespace(store=history,live_stores=stores,server_port=8775)
            for region in ['Toronto','Florida','Toronto']:
                h=Handler.__new__(Handler);h.server=server;h.headers={'Host':'127.0.0.1:8775'}
                h.path='/api/network-live?region='+region+'&approximate=true&rotation=site'
                output=[];h.send=lambda value,*a,**k:output.append(value)
                with patch('dashboard.server.sites',return_value=sites):h.do_GET()
                snapshots=output[0]['snapshots']
                self.assertEqual(len(snapshots),1)
                self.assertEqual(snapshots[0]['objects'][0]['id'],region+'-car')
            self.assertIs(server.store,history)
            self.assertIs(live_store(SimpleNamespace(store=history),sites[0]),history)
