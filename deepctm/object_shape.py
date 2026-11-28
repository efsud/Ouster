"""Visible LiDAR bounding-box descriptors; not a vehicle fingerprint."""
import math
from statistics import median

def dimensions(obj):
    try:w=float(obj.get('width',0));l=float(obj.get('length',0))
    except (ValueError,TypeError):return None
    if not math.isfinite(w+l) or min(w,l)<=.1 or max(w,l)>30:return None
    return [min(w,l),max(w,l)]

def summarize(values):
    values=[v for v in values if v is not None]
    if len(values)<3:return None
    w=median(v[0] for v in values);l=median(v[1] for v in values)
    return {'width_m':w,'length_m':l,'width_mad_m':median(abs(v[0]-w) for v in values),'length_mad_m':median(abs(v[1]-l) for v in values),'samples':len(values)}

def discrepancy(a,b):
    if not a or not b:return None
    try:
        terms=[]
        for name,floor in [('width',.12),('length',.15)]:
            x,y=a[name+'_m'],b[name+'_m']
            if min(x,y)<=0:return None
            scale=max(floor,1.4826*(a[name+'_mad_m']/x+b[name+'_mad_m']/y))
            terms.append(abs(math.log(x/y))/scale)
        return sum(terms)/len(terms)
    except (KeyError,ValueError,TypeError,ZeroDivisionError):return None
