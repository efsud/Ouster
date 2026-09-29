import unittest
from types import SimpleNamespace
from dashboard.public_view import permitted,public_payload,PublicHandler

class PublicViewTest(unittest.TestCase):
    def test_allowlist_excludes_raw_files_and_mutations(self):
        for path in ['/api/received','/data/ouster.sqlite3','/config/sites.local.json','/../data/ouster.sqlite3','/api/collect','/api/process']:
            self.assertFalse(permitted(path))
        for path in ['/','/app.js','/api/network-live','/api/recorded-summary']:self.assertTrue(permitted(path))
    def test_all_writes_denied(self):
        h=PublicHandler.__new__(PublicHandler);results=[];h.respond=lambda b,status=200:results.append(status)
        for fn in [h.do_POST,h.do_PUT,h.do_DELETE,h.do_PATCH]:fn()
        self.assertEqual(results,[403]*4)
    def test_private_metadata_removed(self):
        p=public_payload('/api/status',{'sites':[{'id':'S','scene':{'private':True},'name':'Site'}],'credentials_configured':True})
        self.assertTrue(p['public_view']);self.assertNotIn('credentials_configured',p);self.assertNotIn('scene',p['sites'][0])
        a=public_payload('/api/anomalies',{'items':[{'note':'private review','rule':'stale'}]})
        self.assertNotIn('note',a['items'][0])
