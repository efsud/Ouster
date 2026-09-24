import json
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from dashboard.server import Handler
from dashboard.storage import Store
from dashboard.demo import generate
from scripts.review_anomalies import review


class InterfaceTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=Store(Path(self.tmp.name)/'db')
    def tearDown(self):self.tmp.cleanup()
    def request(self,path,body=None):
        h=Handler.__new__(Handler);h.server=SimpleNamespace(store=self.store,server_port=8765)
        h.path=path;h.headers={'Host':'127.0.0.1:8765','Content-Type':'application/json'};result=[]
        h.send=lambda value,status=200,**kwargs:result.append((value,status,kwargs))
        if body is None:h.do_GET()
        else:
            payload=json.dumps(body).encode();h.headers['Content-Length']=str(len(payload));h.rfile=BytesIO(payload);h.do_POST()
        return result[0]
    def test_received_pagination_and_unknown_anomaly(self):
        self.store.save_batch([dict(site='S',session='x',sensor_time=i,received_at=i,status='received',event={'timestamp':i}) for i in range(3)])
        result,status,_=self.request('/api/received?site=S&limit=2')
        self.assertEqual(status,200);self.assertEqual(len(result['items']),2);self.assertIsNotNone(result['next_cursor'])
        self.assertEqual(self.request('/api/anomaly?id=missing')[1],404)
    def test_anomaly_detail_and_ack(self):
        self.store.save_anomaly(dict(id='a',site='S',category='traffic',rule='queue',start=1,evidence={'validation':'provisional'}))
        self.assertEqual(self.request('/api/anomaly?id=a')[0]['evidence']['validation'],'provisional')
        self.assertTrue(self.request('/api/anomalies/acknowledge',{'id':'a','note':'Checked sample'})[0]['acknowledged'])
        self.assertEqual(self.request('/api/anomaly?id=a')[0]['note'],'Checked sample')
    def test_history_pagination_export_and_evidence(self):
        self.store.save_windows(generate())
        result,_,_=self.request('/api/history?paged=true&limit=2')
        self.assertEqual(len(result['items']),2);self.assertEqual(result['next_offset'],2)
        csv,_,_=self.request('/api/export.csv?paged=true&limit=2&offset=20')
        self.assertEqual(len(csv.splitlines()),37)
    def test_manual_review_counts_and_missing_evidence(self):
        cases=[dict(id=str(i),label=a,detected=b,evidence='synthetic fixture') for i,(a,b) in enumerate([(True,True),(True,False),(False,True),(False,False)])]
        r=review({'cases':cases});self.assertEqual(r['precision'],.5);self.assertEqual(r['recall'],.5)
        cases[0]['evidence']=''
        with self.assertRaises(ValueError):review({'cases':cases})

if __name__=='__main__':unittest.main()
