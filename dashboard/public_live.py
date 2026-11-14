"""Minimal read-only public surface for the two live corridors; no raw/history access."""
from http.server import ThreadingHTTPServer
from urllib.parse import urlsplit
from .server import Handler, ROOT
from .storage import Store

ASSETS={'/','/index.html','/app.js','/road-headings.json','/style.css','/vendor/leaflet.js','/vendor/leaflet.css',
        '/vendor/images/marker-icon.png','/vendor/images/marker-icon-2x.png','/vendor/images/marker-shadow.png','/vendor/images/layers.png','/vendor/images/layers-2x.png'}
ALLOWED=ASSETS|{'/api/status','/api/network-live'}

class PublicHandler(Handler):
    def allowed_host(self):return True  # Only the explicitly allowlisted read surface below.
    def do_GET(self):
        if urlsplit(self.path).path not in ALLOWED:return self.send({'error':'Not available in public live viewer'},403)
        return super().do_GET()
    def do_POST(self):return self.send({'error':'Public viewer is read-only'},405)
    do_PUT=do_POST
    do_DELETE=do_POST
    do_PATCH=do_POST
    def send(self,value,status=200,mime='application/json',**kwargs):
        if mime=='application/json' and isinstance(value,dict):
            if 'sites' in value:
                value={k:v for k,v in value.items() if k!='credentials_configured'}
                value['public_live_only']=True
            if 'snapshots' in value:
                for s in value['snapshots']:
                    s.pop('session',None);s.pop('event_key',None)
                    h=s.get('health') or {}
                    s['health']={k:h[k] for k in ['state','error','last_receipt','recording_mode'] if k in h}
        return super().send(value,status,mime,**kwargs)

def main():
    server=ThreadingHTTPServer(('127.0.0.1',8776),PublicHandler)
    server.store=Store(ROOT/'data/finch-live.sqlite3')
    server.live_stores={'Toronto':server.store,'Florida':Store(ROOT/'data/florida-live.sqlite3')}
    print('Public read-only origin: http://127.0.0.1:8776',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()

if __name__=='__main__':main()
