"""Bounded local Hermite interpolation using motion on both sides of a gap."""
import math
from statistics import median
VEHICLES={str(i) for i in [1,2,3,4,5,6,7,8,9,15]}
MAX_GAP=30.

def bridge(before,after):
    # points: receipt time, along, across, speed, sensor datetime
    if len(before)<3 or len(after)<3:return None
    a,b=before[-1],after[0];duration=b[0]-a[0]
    if not 3<duration<=MAX_GAP:return None
    try:sensor_dt=(b[4]-a[4]).total_seconds()
    except (TypeError,AttributeError):return None
    if not .8<=sensor_dt/duration<=1.2:return None
    def velocity(points):
        slopes=[]
        for p,q in zip(points,points[1:]):
            dt=q[0]-p[0]
            if not 0<dt<=1.5:return None
            slopes.append(((q[1]-p[1])/dt,(q[2]-p[2])/dt))
        if points[-1][0]-points[0][0]<1:return None
        return tuple(median(s[i] for s in slopes) for i in [0,1])
    v0=velocity(before[-5:]);v1=velocity(after[:5])
    if v0 is None or v1 is None:return None
    dx=b[1]-a[1];sign=1 if dx>=0 else -1
    if abs(b[2]-a[2])>4 or any(v[0]*sign<-.5 for v in [v0,v1]):return None
    if max(abs(v0[0]),abs(v1[0]))<.5 and abs(dx)>5:return None
    expected=(v0[0]+v1[0])*.5*duration
    if abs(dx-expected)>max(8.,.5*abs(expected)):return None
    result=[]
    for j in range(math.ceil(duration*2)+1):
        u=j/math.ceil(duration*2);coords=[];vel=[];acc=[]
        for axis in [0,1]:
            p=a[axis+1];q=b[axis+1];m=v0[axis]*duration;n=v1[axis]*duration
            coords.append((2*u**3-3*u*u+1)*p+(u**3-2*u*u+u)*m+(-2*u**3+3*u*u)*q+(u**3-u*u)*n)
            vel.append(((6*u*u-6*u)*p+(3*u*u-4*u+1)*m+(-6*u*u+6*u)*q+(3*u*u-2*u)*n)/duration)
            acc.append(((12*u-6)*p+(6*u-4)*m+(-12*u+6)*q+(6*u-2)*n)/duration**2)
        speed=math.hypot(*vel)
        if speed>35 or math.hypot(*acc)>4 or vel[0]*sign<-.5:return None
        if abs(coords[0])>120 or abs(coords[1])>18:return None
        result.append([a[0]+u*duration,coords[0],speed])
    return result
