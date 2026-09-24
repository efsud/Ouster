"""Read-only field-session audit; missing real evidence yields incomplete status."""
import argparse
import json
from pathlib import Path
import sqlite3
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from dashboard.analytics import percentile

def audit(path,sites,start,end):
    output=[]
    with sqlite3.connect('file:'+str(Path(path).resolve())+'?mode=ro',uri=True) as db:
        db.row_factory=sqlite3.Row
        for site in sites:
            events=db.execute("SELECT count(*) n,min(received_at) first,max(received_at) last FROM raw_events WHERE site=? AND source='sdk' AND status='received' AND received_at BETWEEN ? AND ?",(site,start,end)).fetchone()
            rows=db.execute('SELECT * FROM latency_samples WHERE site=? AND received_at BETWEEN ? AND ?',(site,start,end)).fetchall()
            render=[r['displayed_at']-r['received_at'] for r in rows]
            upstream=[r['received_at']-r['sensor_time'] for r in rows if r['sensor_time'] is not None]
            span=events['last']-events['first'] if events['n'] else 0
            p95=percentile(render,.95)
            output.append({'site':site,'events':events['n'],'observed_span_s':span,'display_samples':len(rows),'receipt_to_display_p95_s':p95,'upstream_p95_s':percentile(upstream,.95),'latency_target_pass':p95 is not None and p95<=2,'thirty_minute_span_pass':span>=1800,'controlled_interruption':'manual evidence required','field_validated':False})
    return {'start':start,'end':end,'sites':output,'note':'Clock synchronization, calibration, sustained coverage and controlled interruption require independent review. This report cannot certify those from event counts alone.'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--db',default='data/ouster.sqlite3');p.add_argument('--start',type=float,required=True);p.add_argument('--end',type=float,default=time.time());a=p.parse_args()
    configured=json.loads((Path(__file__).resolve().parents[1]/'config/sites.json').read_text())['sites']
    print(json.dumps(audit(a.db,[s['id'] for s in configured if s['region']=='Toronto'],a.start,a.end),indent=2))
