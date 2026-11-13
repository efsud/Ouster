import unittest
from unittest.mock import patch
from dashboard.public_live import PublicHandler
from dashboard.server import Handler

class PublicLiveTest(unittest.TestCase):
    def test_only_live_gets_are_forwarded(self):
        for path in ['/api/received','/api/export.csv','/api/anomalies','/api/site-kpis','/api/deepctm','/../config/sites.local.json','/%2e%2e/.env']:
            h=PublicHandler.__new__(PublicHandler);h.path=path;responses=[]
            h.send=lambda value,status=200,**kw:responses.append(status)
            with patch.object(Handler,'do_GET') as forwarded:h.do_GET();forwarded.assert_not_called()
            self.assertEqual(responses,[403])
        for path in ['/','/app.js','/api/status','/api/network-live?region=Florida']:
            h=PublicHandler.__new__(PublicHandler);h.path=path
            with patch.object(Handler,'do_GET') as forwarded:h.do_GET();forwarded.assert_called_once()
    def test_mutations_blocked_and_status_sanitized(self):
        h=PublicHandler.__new__(PublicHandler)
        with patch.object(Handler,'send') as send:
            h.do_POST();self.assertEqual(send.call_args.args[1],405)
            h.send({'sites':[],'credentials_configured':True})
            payload=send.call_args.args[0]
            self.assertNotIn('credentials_configured',payload);self.assertTrue(payload['public_live_only'])
