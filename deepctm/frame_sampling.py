"""Stable figure sampling from the durable full-rate journal; never fills gaps."""
import math

def sample(rows,interval):
    if not math.isfinite(interval) or interval<0:raise ValueError('Invalid processing interval')
    if interval==0:return rows
    output=[];last={}
    for row in rows:
        session,stamp=row[:2]
        if stamp-last.get(session,float('-inf'))>=interval:
            output.append(row);last[session]=stamp
    return output
