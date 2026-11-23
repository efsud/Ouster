"""Experimental retrospective sensor-elapsed timeline, never a timezone assertion.

One fixed offset per sensor/session preserves SDK time differences. Receipt times
are retained and an unstable/reset clock is rejected, not silently repaired.
"""
from datetime import datetime
from statistics import median
import math

def align(rows,max_rate_error=.01,min_span=120):
    """rows are (receipt_seconds, sensor_timestamp). Return times or unavailable."""
    if len(rows)<20:return {'state':'unavailable','reason':'insufficient_clock_samples'}
    try:
        stamps=[datetime.fromisoformat(text) for _,text in rows]
        base=stamps[0];elapsed=[(stamp-base).total_seconds() for stamp in stamps]
    except (TypeError,ValueError):return {'state':'unavailable','reason':'invalid_or_mixed_clock'}
    receipts=[float(r) for r,_ in rows]
    if not all(math.isfinite(r) for r in receipts):return {'state':'unavailable','reason':'nonfinite_receipt'}
    if any(b<=a for a,b in zip(elapsed,elapsed[1:])):return {'state':'unavailable','reason':'sensor_clock_reset_duplicate_or_reordering'}
    if elapsed[-1]-elapsed[0]<min_span:return {'state':'unavailable','reason':'short_clock_span'}
    n=max(5,len(rows)//10)
    sensor_span=median(elapsed[-n:])-median(elapsed[:n]);receipt_span=median(receipts[-n:])-median(receipts[:n])
    rate=receipt_span/sensor_span
    if abs(rate-1)>max_rate_error:return {'state':'unavailable','reason':'clock_rate_or_latency_drift','receipt_to_sensor_rate':rate}
    offsets=[r-t for r,t in zip(receipts,elapsed)];anchor=median(offsets)
    times=[anchor+t for t in elapsed];residuals=[r-t for r,t in zip(receipts,times)]
    return {'state':'candidate','times':times,'anchor_receipt_epoch':anchor,'receipt_to_sensor_rate':rate,
            'receipt_residual_min_s':min(residuals),'receipt_residual_max_s':max(residuals),
            'basis':'sensor elapsed time anchored to median receipt offset; absolute clock synchronization unverified',
            'retrospective_only':True}

def replay_memory(db):
    """Transform ONLY an owned in-memory database copy; original receipts in payload.

    Rejecting a clock removes that session from this experimental copy. Callers
    must display the returned exclusions and retain the source database untouched.
    """
    import json
    import sqlite3
    database=db.execute('PRAGMA database_list').fetchone()[2]
    if database:raise ValueError('Clock experiment requires an in-memory database')
    evidence=[]
    for site,session in db.execute('SELECT DISTINCT site,session FROM frames').fetchall():
        rows=db.execute('SELECT event_key,received,payload FROM frames WHERE site=? AND session=? ORDER BY received',(site,session)).fetchall()
        decoded=[json.loads(payload) for _,_,payload in rows]
        samples=[(received,raw.get('frame',{}).get('timestamp') or raw.get('timestamp')) for (_,received,_),raw in zip(rows,decoded)]
        result=align(samples);record={k:v for k,v in result.items() if k not in ('times','anchor_receipt_epoch')};record.update(site=site,samples=len(rows));evidence.append(record)
        if result['state']!='candidate':
            db.execute('DELETE FROM frames WHERE site=? AND session=?',(site,session));continue
        for (key,received,_),raw,t in zip(rows,decoded,result['times']):
            raw['_collector_received_at']=received
            db.execute('UPDATE frames SET received=?,payload=? WHERE site=? AND session=? AND event_key=?',(t,json.dumps(raw),site,session,key))
    db.commit();return evidence

def align_frames(rows):
    """Return (session, plot_time, payload, original_receipt) and clock audit."""
    import json
    from collections import defaultdict
    grouped=defaultdict(list);output=[];audit=[]
    for session,receipt,payload in rows:grouped[session].append((receipt,payload))
    for session,values in grouped.items():
        decoded=[json.loads(payload) for _,payload in values]
        samples=[(receipt,raw.get('frame',{}).get('timestamp') or raw.get('timestamp')) for (receipt,_),raw in zip(values,decoded)]
        result=align(samples);audit.append({k:v for k,v in result.items() if k not in ('times','anchor_receipt_epoch')}|{'session':session,'samples':len(values)})
        if result['state']!='candidate':continue
        output.extend((session,t,payload,receipt) for t,(receipt,payload) in zip(result['times'],values))
    return sorted(output,key=lambda row:row[1]),audit
