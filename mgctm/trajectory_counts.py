"""Verified gate crossings from original Ouster frames; cars are SDK class 2."""
from collections import Counter, defaultdict
from datetime import datetime
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo

from .geometry import write_csv

FIELDS=('date','peak','end_s','target','metric','value','source')


def sensor_seconds(stamp):
    clock=datetime.fromisoformat(stamp)
    if clock.utcoffset() is None:
        raise ValueError('Absolute sensor timestamp must carry a verified UTC offset')
    return clock.timestamp()


def crosses(a,b,p,q):
    """Directed crossing of a finite gate p→q, from its right to its left."""
    dx,dy=q[0]-p[0],q[1]-p[1]
    def side(r):
        return dx*(r[1]-p[1])-dy*(r[0]-p[0])
    u,v=side(a),side(b)
    if not u<0<=v:
        return None
    f=-u/(v-u)
    x,y=(a[i]+f*(b[i]-a[i]) for i in range(2))
    s=((x-p[0])*dx+(y-p[1])*dy)/(dx*dx+dy*dy)
    return f if 0<=s<=1 else None


def bin_counts(records, gates, start, end, bin_s, max_gap_s=1, max_clock_offset_s=3):
    n=round((end-start)/bin_s)
    if (n<1 or not math.isclose(n*bin_s,end-start) or
            not 0<max_gap_s<=3 or not 0<max_clock_offset_s<=30):
        raise ValueError('Invalid bin width or configured clock tolerances')
    bad=set()
    coverage=defaultdict(float)
    counts=Counter()
    previous={}
    prev_time=prev_receipt=prev_session=None
    broken=Counter()
    for r in records:
        payload=r['payload']
        if not isinstance(frame:=payload.get('frame'),dict):
            continue
        receipt=r['received_at']
        try:
            t=sensor_seconds(frame.get('timestamp') or payload['timestamp'])
            if abs(t-receipt)>max_clock_offset_s:
                raise ValueError('Sensor time does not match audited receipt clock')
        except (KeyError,TypeError,ValueError):
            bad.add(math.floor((receipt-start)/bin_s))
            broken['clock_invalid']+=1
            previous={};prev_time=prev_receipt=prev_session=None
            continue
        session=r['session']
        same=prev_session==session and prev_time is not None
        dt=t-prev_time if same else 0
        dr=receipt-prev_receipt if same else 0
        valid=same and 0<dt<=max_gap_s and 0<dr<=max_gap_s and .5<=dt/dr<=2
        if valid:
            for j in range(max(0,math.floor((prev_time-start)/bin_s)),min(n,math.floor((t-start)/bin_s)+1)):
                coverage[j]+=max(0,min(t,start+(j+1)*bin_s)-max(prev_time,start+j*bin_s))
        elif prev_time is not None:
            broken['frame_pair_break']+=1
            if same and dt<=0:
                bad.add(math.floor((t-start)/bin_s))
        current={}
        for obj in frame.get('objects',[]):
            if str(obj.get('classType'))!='2':
                continue
            try:
                ident=str(obj['id']);p=(float(obj['centerX']),float(obj['centerY']))
                if not ident or not all(map(math.isfinite,p)):
                    raise ValueError
            except (KeyError,TypeError,ValueError):
                broken['invalid_car']+=1
                bad.add(math.floor((t-start)/bin_s))
                continue
            if ident in current:
                broken['duplicate_id']+=1
                bad.add(math.floor((t-start)/bin_s))
                continue
            current[ident]=p
            if not valid or ident not in previous:
                continue
            a=previous[ident]
            if math.dist(a,p)/dt>60:
                broken['implausible_car_jump']+=1
                bad.add(math.floor((t-start)/bin_s))
                continue
            for g in gates:
                f=crosses(a,p,g['p'],g['q'])
                if f is not None:
                    j=math.floor((prev_time+f*dt-start)/bin_s)
                    if 0<=j<n:counts[g['target'],j]+=1
        previous=current;prev_time=t;prev_receipt=receipt;prev_session=session
    # Use only bins with essentially complete frame coverage. Do not scale up
    # counts or interpret missing observations as zero.
    valid_bins={j for j in range(n) if j not in bad and
                coverage[j]>=bin_s-max_gap_s-1e-6 and coverage[j]<=bin_s+1e-6}
    return counts,valid_bins,dict(coverage_s=[round(coverage[j],3) for j in range(n)],
                                 valid_bins=sorted(valid_bins),breaks=dict(broken))


def convert(capture, gatefile, output):
    from deepctm.florida_tracks import events
    capture=Path(capture); output=Path(output)
    g=json.loads(Path(gatefile).read_text())
    m=json.loads((capture/'manifest.json').read_text())
    if m['state']!='captured' or g.get('sensor_clock_verified') is not True:
        raise ValueError('Need a completed capture and independently verified sensor clock')
    if not g.get('gates') or g['peak'] not in ('AM','PM'):
        raise ValueError('Need verified car-count gates and AM/PM label')
    local=datetime.fromtimestamp(m['start'],ZoneInfo('America/New_York'))
    local_end=datetime.fromtimestamp(m['end'],ZoneInfo('America/New_York'))
    expected={'AM':(7,9),'PM':(16,18)}[g['peak']]
    if (local.date()!=local_end.date() or (local.hour,local_end.hour)!=expected
        or any((local.minute,local.second,local.microsecond,local_end.minute,local_end.second,local_end.microsecond))):
        raise ValueError('Capture must align exactly to the declared two-hour peak window')
    gates=defaultdict(list); targets=set()
    for gate in g['gates']:
        if gate['site'] not in m['sites'] or gate['target'] in targets or not gate.get('source'):
            raise ValueError('Unique gate targets, known sensors and calibration sources required')
        p,q=gate['p'],gate['q']
        if len(p)!=2 or len(q)!=2 or not all(map(math.isfinite,[*p,*q])) or math.dist(p,q)<.1:
            raise ValueError('Invalid finite directed gate in local sensor metres')
        targets.add(gate['target']);gates[gate['site']].append(gate)
    out=[]; audits={}
    for site,items in gates.items():
        issues=Counter()
        counts,bins,audit=bin_counts(events(capture,site,issues),items,m['start'],m['end'],g['bin_s'])
        audit['archive_issues']=dict(issues)
        audits[site]=audit
        if issues:
            continue
        for gate in items:
            for j in sorted(bins):
                out.append(dict(date=local.date().isoformat(),peak=g['peak'],end_s=(j+1)*g['bin_s'],
                    target=gate['target'],metric='count',value=counts[gate['target'],j],
                    source=f"Ouster {capture.name}/{site} class 2; {gate['source']}"))
    output.parent.mkdir(parents=True,exist_ok=True)
    write_csv(output,out,FIELDS)
    output.with_suffix('.audit.json').write_text(json.dumps(audits,indent=2))
    return dict(rows=len(out),sites=len(gates),file=str(output))
