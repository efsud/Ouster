"""Loopback-only, read-only SR-436 dashboard. Never serves raw archives."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
from .florida_capture import BASE, CONFIG, ROOT

STATIC = ROOT / 'dashboard/static'


def locate(base):
    value = json.loads((base/'latest.json').read_text())['capture_id']
    if not re.fullmatch(r'\d{8}T\d{6}Z-[a-f0-9]{6}', value):
        raise ValueError('Invalid capture ID')
    folder = (base/value).resolve()
    if not folder.is_relative_to(base.resolve()):
        raise ValueError('Invalid capture path')
    return folder


def dashboard_status(base):
    try:
        d = locate(base)
    except FileNotFoundError:
        return {'state': 'not_started', 'sites': json.loads(CONFIG.read_text())['sites']}
    m = json.loads((d/'manifest.json').read_text())
    cfg = json.loads((d/'config.json').read_text())
    rows = []
    for site in cfg['sites']:
        ident = site['id']
        path = d/(ident+'-status.json')
        status = json.loads(path.read_text()) if path.exists() else {}
        rows.append({**site, **status, 'unavailable': m.get('unavailable', {}).get(ident)})
    return {**m, 'capture_id': d.name, 'sites': rows, 'observed': (d/'observed/index.json').is_file()}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        port = self.server.server_port
        if self.headers.get('Host') not in {f'127.0.0.1:{port}', f'localhost:{port}'}:
            self.send_error(403)
            return
        headers = {}
        try:
            if self.path == '/':
                body, mime = (STATIC/'sr436.html').read_bytes(), 'text/html; charset=utf-8'
            elif self.path == '/sr436.js':
                body, mime = (STATIC/'sr436.js').read_bytes(), 'text/javascript; charset=utf-8'
            elif self.path == '/api/status':
                body, mime = json.dumps(dashboard_status(self.server.base)).encode(), 'application/json'
            elif self.path == '/api/observed/index.json':
                body, mime = (locate(self.server.base)/'observed/index.json').read_bytes(), 'application/json'
            elif (match := re.fullmatch(r'/api/observed/(\d{8}T\d{6}Z-[a-f0-9]{6})/(OBC-AG-SA-C\d{6})', self.path)):
                d = locate(self.server.base)
                if match[1] != d.name or match[2] not in json.loads((d/'manifest.json').read_text())['sites']:
                    self.send_error(404)
                    return
                body, mime = (d/'observed'/(match[2]+'.json.gz')).read_bytes(), 'application/json'
                headers['Content-Encoding'] = 'gzip'
            else:
                self.send_error(404)
                return
        except FileNotFoundError:
            self.send_error(404)
            return
        except (OSError, ValueError, KeyError):
            self.send_error(503)
            return
        self.send_response(200)
        for k, v in {'Content-Type': mime, 'Content-Length': str(len(body)),
                     'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff', **headers}.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--port', type=int, default=8770)
    p.add_argument('--base', type=Path, default=BASE)
    args = p.parse_args()
    with ThreadingHTTPServer(('127.0.0.1', args.port), Handler) as server:
        server.base = args.base
        print(f'Florida speed viewer: http://127.0.0.1:{server.server_port}/', flush=True)
        server.serve_forever()
