"""Read-only public gateway. Expose this port, never the administrative server."""
import argparse
import json
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import urlopen
from urllib.error import HTTPError,URLError

STATIC=Path(__file__).resolve().parent/'static'
READ_API={'/api/status','/api/network-live','/api/live','/api/history','/api/export.csv','/api/recorded-summary','/api/availability','/api/ctm','/api/anomalies','/api/anomaly-evaluations'}
STATIC_PATHS={'/'}|{'/'+p.relative_to(STATIC).as_posix() for p in STATIC.rglob('*') if p.is_file()}

def permitted(path):return path in READ_API or path in STATIC_PATHS

def public_payload(path,payload):
    if path=='/api/status':
        payload['public_view']=True
        payload.pop('credentials_configured',None)
        payload['sites']=[{k:v for k,v in site.items() if k in {'id','name','region','corridor','timezone','reference_location','origin','rotation_deg','calibration_status'}} for site in payload['sites']]
    if path=='/api/anomalies':
        for event in payload['items']:event.pop('note',None)
    return payload

class PublicHandler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def respond(self,body,status=200,mime='application/json'):
        if isinstance(body,dict):body=json.dumps(body).encode()
        self.send_response(status);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https://tile.openstreetmap.org; connect-src 'self'; frame-ancestors 'none'")
        self.end_headers()
        if self.command!='HEAD':self.wfile.write(body)
    def do_GET(self):
        parsed=urlsplit(self.path)
        if parsed.scheme or parsed.netloc or len(self.path)>4096:return self.respond({'error':'Invalid request'},400)
        if parsed.path=='/api/window':return self.respond({'notice':'Detailed observation evidence is available only in the local dashboard.'})
        if not permitted(parsed.path):return self.respond({'error':'Not available in public view'},403)
        try:
            with urlopen(f'http://127.0.0.1:{self.server.upstream_port}'+self.path,timeout=20) as upstream:
                body=upstream.read();mime=upstream.headers.get('Content-Type','application/octet-stream')
                if parsed.path in {'/api/status','/api/anomalies'}:body=json.dumps(public_payload(parsed.path,json.loads(body))).encode()
                self.respond(body,mime=mime)
        except HTTPError as exc:self.respond({'error':'Dashboard request unavailable'},exc.code)
        except (URLError,TimeoutError):self.respond({'error':'Local dashboard is offline'},503)
    do_HEAD=do_GET
    def do_POST(self):self.respond({'error':'Public view is read-only; use the local dashboard for changes.'},403)
    do_PUT=do_POST
    do_DELETE=do_POST
    do_PATCH=do_POST

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--port',type=int,default=8769);p.add_argument('--upstream-port',type=int,default=8765);a=p.parse_args()
    server=ThreadingHTTPServer(('127.0.0.1',a.port),PublicHandler);server.upstream_port=a.upstream_port
    print(f'Read-only gateway on 127.0.0.1:{a.port}',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
