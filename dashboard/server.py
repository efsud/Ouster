"""Local dashboard server. Bind only to loopback; not an internet deployment."""
import argparse
import csv
from datetime import datetime
import io
import json
import os
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import time
from urllib.parse import urlparse, parse_qs
from urllib.error import HTTPError, URLError
from .analytics import METRICS, calculate, finite, local_to_geo, simulate
from .bluecity import BlueCity
from .storage import Store
from .demo import generate
from .live import snapshot, approximate_snapshot
from .calibration import report as calibration_report
from .processing import process_range, calendar_bounds
from .anomalies import evaluate_traffic, evaluate_health
from .worker import start_worker

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT/'dashboard/static'

def sites():
    local = ROOT/'config/sites.local.json'
    entries = json.loads((ROOT/'config/sites.json').read_text())['sites']
    if local.exists():
        overrides = json.loads(local.read_text())['sites']
        mapping = {s['id']:s for s in entries}
        for s in overrides: mapping[s['id']] = {**mapping.get(s['id'],{}),**s}
        entries = list(mapping.values())
    return entries

def corridors():
    """Only locally supplied, verified GeoJSON-style LineStrings are exposed."""
    local=ROOT/'config/sites.local.json'
    if not local.exists(): return []
    result=[]
    for corridor in json.loads(local.read_text()).get('corridors',[]):
        if corridor.get('geometry_verified') is not True: continue
        points=corridor.get('coordinates',[])
        if not isinstance(points,list) or len(points)<2:
            raise ValueError('A verified corridor needs at least two [longitude,latitude] points')
        for point in points:
            if not isinstance(point,list) or len(point)!=2:
                raise ValueError('Corridor points must be [longitude,latitude] pairs')
            lng,lat=point
            finite(lng,'corridor longitude');finite(lat,'corridor latitude')
            if not -180<=lng<=180 or not -85<lat<85:
                raise ValueError('Corridor coordinates outside supported range')
        result.append({'name':str(corridor['name']),'region':str(corridor['region']),'coordinates':points})
    return result

def validate_window(w):
    if not isinstance(w,dict): raise ValueError('Each window must be an object')
    known = {s['id'] for s in sites()}
    if w.get('site') not in known: raise ValueError('Unknown site; add verified metadata to config/sites.local.json')
    if not isinstance(w.get('approach'),str) or not w['approach'] or len(w['approach'])>50:
        raise ValueError('A nonempty approach of at most 50 characters is required')
    if w.get('source') != 'annotated-import': raise ValueError('Imported KPI windows must use source annotated-import')
    return calculate(w)

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # Do not log user queries or credentials.

    def send(self, value, status=200, mime='application/json', attachment=None):
        body = json.dumps(value,allow_nan=False).encode() if mime=='application/json' else value
        if isinstance(body,str): body=body.encode()
        self.send_response(status)
        self.send_header('Content-Type',mime)
        self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https://tile.openstreetmap.org; connect-src 'self'; frame-ancestors 'none'")
        if attachment: self.send_header('Content-Disposition',f'attachment; filename="{attachment}"')
        self.end_headers(); self.wfile.write(body)

    def allowed_host(self):
        return self.headers.get('Host') in {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}

    def do_GET(self):
        if not self.allowed_host(): return self.send({'error':'Local requests only'},403)
        try:
            parsed = urlparse(self.path)
            q = {k:v[0] for k,v in parse_qs(parsed.query).items()}
            if parsed.path == '/api/status':
                entries=[dict(s,calibration_status=calibration_report(s)) for s in sites()]
                return self.send({'sites':entries,'corridors':corridors(),'metrics':METRICS,'credentials_configured':bool(os.getenv('BLUECITY_USERNAME') and os.getenv('BLUECITY_PASSWORD')),'mode':'read-only','toronto_configured':any(s.get('region')=='Toronto' for s in entries)})
            if parsed.path == '/api/received':
                return self.send(self.server.store.raw_page(q.get('site'),float(q['start']) if q.get('start') else None,float(q['end']) if q.get('end') else None,int(q.get('cursor',0)),max(1,min(1000,int(q.get('limit',100))))))
            if parsed.path == '/api/availability':
                return self.send(self.server.store.availability(q.get('site')))
            if parsed.path == '/api/window':
                result=self.server.store.window_input(q['site'],q['approach'],float(q['start']),float(q['end']),q['source'])
                return self.send(result if result else {'error':'Window not found'},200 if result else 404)
            if parsed.path == '/api/anomaly':
                with self.server.store.connect() as db:
                    row=db.execute('SELECT * FROM anomalies WHERE id=?',(q['id'],)).fetchone()
                return self.send({**dict(row),'evidence':json.loads(row['evidence'])} if row else {'error':'Anomaly not found'},200 if row else 404)
            if parsed.path == '/api/anomalies':
                return self.send(self.server.store.anomaly_page(q.get('site'),q.get('category'),max(0,int(q.get('offset',0))),max(1,min(500,int(q.get('limit',100))))))
            if parsed.path == '/api/anomaly-evaluations':
                with self.server.store.connect() as db:
                    rows=db.execute('SELECT * FROM evaluations WHERE site=? ORDER BY start DESC LIMIT 100',(q.get('site'),)).fetchall()
                return self.send([{**dict(r),'evidence':json.loads(r['evidence'])} for r in rows])
            if parsed.path == '/api/network-live':
                entries=[s for s in sites() if s.get('region')==q.get('region')]
                now=time.time()
                rotation=finite(float(q.get('rotation',180)),'rotation')
                return self.send({'snapshots':[approximate_snapshot(self.server.store,s,now,rotation) if q.get('approximate')=='true' else snapshot(self.server.store,s,now) for s in entries]})
            if parsed.path == '/api/live':
                site = next((s for s in sites() if s['id']==q.get('site')),None)
                if not site: raise ValueError('Select a configured site')
                return self.send(snapshot(self.server.store,site))
            if parsed.path in ['/api/history','/api/export.csv']:
                page_limit=max(1,min(1000,int(q.get('limit',1000))));offset=max(0,int(q.get('offset',0)))
                rows = self.server.store.history(q.get('site'),float(q['start']) if q.get('start') else None,float(q['end']) if q.get('end') else None,q.get('source'),q.get('approach'),limit=-1 if parsed.path.endswith('.csv') else page_limit+1 if q.get('paged')=='true' else 10000,offset=0 if parsed.path.endswith('.csv') else offset,cadence=q.get('cadence'))
                if parsed.path.endswith('.csv'):
                    buf=io.StringIO(); writer=csv.writer(buf)
                    writer.writerow(['site','approach','start_utc','end_utc','source',*METRICS,'quality','valid_tracks','coverage','flags'])
                    def safe(v): return "'"+v if isinstance(v,str) and v.startswith(('=','+','-','@')) else v
                    for r in rows:
                        writer.writerow([safe(r['site']),safe(r['approach']),r['start'],r['end'],r['source'],*[r['values'][k] for k in METRICS],r['quality']['status'],r['quality']['valid_tracks'],r['quality']['coverage'],'; '.join(r['quality']['flags'])])
                    return self.send(buf.getvalue(),mime='text/csv',attachment='ouster-kpis.csv')
                return self.send({'items':rows[:page_limit],'next_offset':offset+page_limit if len(rows)>page_limit else None} if q.get('paged')=='true' else rows)
            if parsed.path == '/api/ctm':
                params = {k:float(v) for k,v in q.items() if k in ['demand','green','cycle','offset']}
                if 'intersections' in q: params['intersections']=int(q['intersections'])
                return self.send(simulate(params))
            path = (STATIC/('index.html' if parsed.path=='/' else parsed.path.lstrip('/'))).resolve()
            if not path.is_relative_to(STATIC) or not path.is_file(): return self.send({'error':'Not found'},404)
            mime = {'.html':'text/html; charset=utf-8','.css':'text/css','.js':'text/javascript','.png':'image/png','.svg':'image/svg+xml'}.get(path.suffix,'application/octet-stream')
            return self.send(path.read_bytes(),mime=mime)
        except (ValueError,KeyError,TypeError) as exc:
            self.send({'error':str(exc)},400)

    def do_POST(self):
        origin = self.headers.get('Origin')
        if not self.allowed_host() or origin not in {None,f'http://{self.headers.get("Host")}'}:
            return self.send({'error':'Local requests only'},403)
        if self.headers.get('Content-Type') != 'application/json':
            return self.send({'error':'JSON content type required'},415)
        try:
            length=int(self.headers.get('Content-Length',0))
            if not 0 < length <= 5_000_000: raise ValueError('Request must be between 1 byte and 5 MB')
            body=json.loads(self.rfile.read(length))
            if self.path != '/api/import' and not isinstance(body,dict):
                raise ValueError('Expected a JSON object')
            if self.path == '/api/latency':
                finite(body['displayed_at'],'displayed_at')
                return self.send({'saved':self.server.store.record_latency(body['event_key'],body['displayed_at'])})
            if self.path == '/api/anomalies/acknowledge':
                note=body.get('note','')
                if not isinstance(note,str) or len(note)>2000:raise ValueError('Review note limit is 2000 characters')
                ok=self.server.store.acknowledge(body['id'],note)
                return self.send({'acknowledged':ok},200 if ok else 404)
            if self.path == '/api/process':
                site=next((s for s in sites() if s['id']==body.get('site')),None)
                if not site:raise ValueError('Select a configured site')
                if body.get('cadence')=='daily':a,b=calendar_bounds(body['day'],site.get('timezone','America/Toronto'))
                else:a,b=float(body['start']),float(body['end'])
                result=process_range(self.server.store,site,a,b,body.get('cadence','five_minute'))
                evaluate_traffic(self.server.store,site)
                return self.send(result)
            if self.path == '/api/anomalies/evaluate':
                site=next((s for s in sites() if s['id']==body.get('site')),None)
                if not site:raise ValueError('Select a configured site')
                evaluate_health(self.server.store,site);result=evaluate_traffic(self.server.store,site)
                return self.send({'traffic_events':len(result),'validation':'provisional'})
            if self.path == '/api/demo':
                self.server.store.save_windows(generate())
                return self.send({'saved':36,'source':'synthetic'})
            if self.path == '/api/import':
                if not isinstance(body,list) or not 1<=len(body)<=1000: raise ValueError('Import a JSON list of 1–1000 annotated windows')
                validated=[(w,validate_window(w)) for w in body]
                self.server.store.save_windows(validated)
                return self.send({'saved':len(validated)})
            if self.path == '/api/collect':
                site = next((s for s in sites() if s['id']==body.get('site')),None)
                if not site: raise ValueError('Select a configured site')
                kind=body.get('kind','turning_counts')
                if kind not in ['turning_counts','phases']: raise ValueError('Unsupported collection type')
                params={'UDID':site['id']}
                if kind=='turning_counts':
                    start=datetime.fromisoformat(body['start'].replace('Z','+00:00'))
                    end=datetime.fromisoformat(body['end'].replace('Z','+00:00'))
                    if start.tzinfo is None or end.tzinfo is None: raise ValueError('Timezone-aware dates required')
                    if not 0<(end-start).total_seconds()<=86400: raise ValueError('Collect at most 24 hours per request')
                    params.update(fdate=start.isoformat(),tdate=end.isoformat(),a=1,simplified='false')
                else: params['active_only']='false'
                result=self.server.bluecity.query(kind,params)
                dest=ROOT/'data/cloud'; dest.mkdir(parents=True,exist_ok=True)
                # Filename is generated locally; untrusted identifiers never become paths.
                name=f'{kind}-{time.time_ns()}.json'
                (dest/name).write_text(json.dumps({'site':site['id'],'kind':kind,'params':params,'data':result},indent=2))
                return self.send({'saved':name,'note':'Raw vendor data saved locally; not relabelled as trajectory KPIs'})
            return self.send({'error':'Not found'},404)
        except HTTPError as exc:
            self.send({'error':f'BlueCity returned HTTP {exc.code}; check API account and site permissions'},502)
        except (URLError,TimeoutError):
            self.send({'error':'BlueCity network request failed; no data saved'},502)
        except (ValueError,KeyError,TypeError) as exc:
            self.send({'error':str(exc)},400)

def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--port',type=int,default=8765); args=p.parse_args()
    server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    server.store=Store(os.getenv('OUSTER_DB',str(ROOT/'data/ouster.sqlite3')))
    server.bluecity=BlueCity()
    stop_worker=start_worker(server.store,sites)
    print(f'Ouster dashboard: http://127.0.0.1:{args.port}',flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally:stop_worker.set();server.server_close()

if __name__=='__main__': main()
