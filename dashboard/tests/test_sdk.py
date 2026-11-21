"""No network or real credentials: verify the optional vendor adapter with mocks."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch,Mock
try:
    from dashboard.sdk_client import ObservableConnection
except ImportError:
    ObservableConnection=None
from dashboard.storage import Store

@unittest.skipIf(ObservableConnection is None,'Run with .venv Python for supplied SDK adapter tests')
class SDKTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=str(Path(self.tmp.name)/'db');self.store=Store(self.path)
        self.client=ObservableConnection.__new__(ObservableConnection)
        self.client.store_path=self.path;self.client.site_id='TEST';self.client.auth_server_access='https://core.api.bluecity.ai/api/token/'
        self.client.username='fixture';self.client.password='fixture-not-real'
    def tearDown(self):self.tmp.cleanup()
    def test_denied_auth_is_specific_and_secret_free(self):
        with patch('dashboard.sdk_client.requests.post',return_value=Mock(status_code=401)) as call:
            self.assertFalse(self.client.getToken())
            self.assertEqual(call.call_args.kwargs['timeout'],20)
            self.assertFalse(call.call_args.kwargs['allow_redirects'])
        h=self.store.health('TEST');self.assertEqual(h['error'],'auth_http_401');self.assertNotIn('fixture',str(h))
    def test_auth_success_is_not_reception(self):
        r=Mock(status_code=200);r.json.return_value={'access':'fake','refresh':'fake-refresh'}
        with patch('dashboard.sdk_client.requests.post',return_value=r):self.assertTrue(self.client.getToken())
        self.assertEqual(self.store.health('TEST')['state'],'authenticated')
        self.assertEqual(self.store.availability('TEST')['count'],0)
