"""Small read-only experiment viewer, separate from the live-map DB/maintenance."""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import json
from dashboard.deepctm_status import status,figure_asset

STATIC=Path(__file__).resolve().parents[1]/'dashboard/static'
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        if self.headers.get('Host') not in {'127.0.0.1:8768','localhost:8768'}:self.send_error(403);return
        routes={'/':'deepctm.html','/deepctm.js':'deepctm.js','/style.css':'style.css'}
        try:
            if self.path=='/api/deepctm':body=json.dumps(status(),allow_nan=False).encode();mime='application/json'
            elif self.path.startswith('/api/deepctm/figures/'):
                body,mime=figure_asset(self.path.removeprefix('/api/deepctm/figures/'))
            elif self.path in routes:
                name=routes[self.path];body=(STATIC/name).read_bytes();mime='text/html' if name.endswith('html') else 'text/javascript' if name.endswith('js') else 'text/css'
            else:self.send_error(404);return
        except (OSError,ValueError,KeyError):self.send_error(503,'Experiment status unavailable');return
        self.send_response(200);self.send_header('Content-Type',mime);self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
if __name__=='__main__':ThreadingHTTPServer(('127.0.0.1',8768),Handler).serve_forever()
