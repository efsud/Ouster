"""Retrospective correction of bounded delivery bursts using visible SDK elapsed time.

No absolute SDK timezone is inferred. Each correction has unchanged receipt-time
anchors on both sides, a continuous monotonic sensor clock, and <=1% rate error.
Raw rows and original receipts are preserved. Missing SDK frames are not filled.
"""
from collections import defaultdict,Counter
from datetime import datetime
import json
import numpy as np


def correct(rows,max_span_s=60.,max_delay_s=15.,anchor_tolerance_s=.2,stable_frames=5):
    groups=defaultdict(list)
    for session,receipt,payload in rows:groups[session].append((receipt,payload))
    output=[];audit=[]
    for session,values in groups.items():
        receipts=np.asarray([v[0] for v in values],float);sensor=[]
        for _,payload in values:
            try:
                e=json.loads(payload);stamp=datetime.fromisoformat(e.get('frame',{}).get('timestamp') or e.get('timestamp'))
                # Epoch is used only for subtraction within this session, not as
                # a geographic timezone/UTC assertion.
                sensor.append((stamp.replace(tzinfo=None)-datetime(2000,1,1)).total_seconds())
            except (ValueError,TypeError,KeyError):sensor.append(float('nan'))
        sensor=np.asarray(sensor);times=receipts.copy();events=[];reasons=Counter();i=1
        while i<len(values):
            dr=receipts[i]-receipts[i-1];ds=sensor[i]-sensor[i-1]
            if not(dr>1.5 and 0<ds<=1.5 and dr-ds>=1.):i+=1;continue
            start=i-1;end=None;reason='no_stable_return_anchor'
            if dr-ds>max_delay_s:reasons['delay_above_bound']+=1;i+=1;continue
            offset=receipts[start]-sensor[start]
            for j in range(i,len(values)-stable_frames+1):
                if receipts[j]-receipts[start]>max_span_s:break
                if not 0<sensor[j]-sensor[j-1]<=1.5:
                    reason='sensor_discontinuity';break
                if sensor[j]-sensor[start]<5:continue
                tail=slice(j,j+stable_frames)
                increments=np.diff(sensor[j-1:j+stable_frames])
                if np.any(~np.isfinite(increments)) or np.any(increments<=0) or np.any(increments>1.5):continue
                if np.max(abs(receipts[tail]-sensor[tail]-offset))>anchor_tolerance_s:continue
                rate=(receipts[j]-receipts[start])/(sensor[j]-sensor[start])
                if abs(rate-1)>.01:continue
                proposed=receipts[start]+(sensor[start:j+1]-sensor[start])*rate
                delta=receipts[start:j+1]-proposed
                if np.any(delta<-.25) or np.any(delta>max_delay_s):continue
                end=j;break
            if end is None:reasons[reason]+=1;i+=1;continue
            times[start:end+1]=proposed
            events.append(dict(receipt_start=float(receipts[start]),receipt_end=float(receipts[end]),frames=end-start+1,
                max_receipt_delay_s=float(max(delta)),anchor_rate=float(rate),sensor_elapsed_s=float(sensor[end]-sensor[start])))
            i=end+1
        output.extend((session,float(t),payload,float(receipt)) for t,(receipt,payload) in zip(times,values))
        audit.append(dict(session=session,state='bounded_delivery_correction',frames=len(values),corrected_frames=int(np.sum(abs(times-receipts)>1e-6)),events=events,rejected=dict(reasons),
            basis='continuous SDK elapsed intervals between unchanged receipt anchors; absolute cross-sensor synchronization unverified'))
    return sorted(output,key=lambda r:r[1]),audit
