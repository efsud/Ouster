"""Provisional 12-movement classification from complete 2D intersection tracks.
Coordinates are road-relative: +x eastbound along corridor, +y north-side arm.
Not surveyed lane geometry; phase agreement never determines trajectory identity.
"""
import math
from statistics import median
ARMS=('N','E','S','W')
VECTORS={'N':(0,1),'E':(1,0),'S':(0,-1),'W':(-1,0)}
MOVEMENTS={a+b:{'from':a,'to':b,'turn':('straight' if (ARMS.index(b)-ARMS.index(a))%4==2 else 'left' if (ARMS.index(b)-ARMS.index(a))%4==1 else 'right')} for a in ARMS for b in ARMS if a!=b}

def arm(x,y):
    length=math.hypot(x,y)
    if length<20:return None
    best=max(VECTORS,key=lambda k:x*VECTORS[k][0]+y*VECTORS[k][1])
    return best if (x*VECTORS[best][0]+y*VECTORS[best][1])/length>=math.cos(math.radians(35)) else None

def route(code):
    a,b=code
    incoming={'W':'eastbound','E':'westbound'}.get(a)
    outgoing={'E':'eastbound','W':'westbound'}.get(b)
    role='through' if incoming and outgoing and incoming==outgoing else 'corridor_exit' if incoming else 'corridor_entry' if outgoing else 'cross_street'
    return dict(role=role,incoming_direction=incoming,outgoing_direction=outgoing,can_match_previous=bool(incoming),can_match_next=bool(outgoing))

def classify(points):
    # receipt, along, across; complete approach + departure needed.
    unknown={'state':'unknown','reason':'Incomplete or ambiguous approach/departure geometry','can_match_previous':False,'can_match_next':False}
    if len(points)<8:return unknown
    if any(not 0<b[0]-a[0]<=3 for a,b in zip(points,points[1:])):return unknown
    first=points[:5];last=points[-5:];start=(median(p[1] for p in first),median(p[2] for p in first));finish=(median(p[1] for p in last),median(p[2] for p in last))
    origin=arm(*start);destination=arm(*finish)
    if not origin or not destination or origin==destination:return unknown
    if min(math.hypot(p[1],p[2]) for p in points)>35:return unknown
    def aligned(chunk,direction):
        dx=chunk[-1][1]-chunk[0][1];dy=chunk[-1][2]-chunk[0][2];length=math.hypot(dx,dy)
        return length>=3 and (dx*direction[0]+dy*direction[1])/length>=math.cos(math.radians(40))
    iv=VECTORS[origin];ov=VECTORS[destination]
    initial=[]
    for p in points:
        if arm(p[1],p[2])!=origin:break
        initial.append(p)
    terminal=[]
    for p in reversed(points):
        if arm(p[1],p[2])!=destination:break
        terminal.append(p)
    terminal.reverse()
    if len(initial)<3 or len(terminal)<3 or not aligned(initial,(-iv[0],-iv[1])) or not aligned(terminal,ov):return unknown
    code=origin+destination
    return dict(state='estimated_geometry',movement=code,**MOVEMENTS[code],**route(code),reason='Observed approach and departure in provisional road-relative geometry')

class TrackCollector:
    def __init__(self):self.active={};self.finished=[]
    def flush(self,key):
        points=self.active.pop(key,[])
        if len(points)>=8:self.finished.append(dict(key=key,start=points[0][0],end=points[-1][0],points=points,movement=classify(points)))
    def feed(self,key,t,x,y):
        if not math.isfinite(x+y) or math.hypot(x,y)>180:self.flush(key);return
        old=self.active.get(key)
        if old and (not 0<t-old[-1][0]<=3 or math.hypot(x-old[-1][1],y-old[-1][2])/(t-old[-1][0])>45):self.flush(key)
        self.active.setdefault(key,[]).append((t,x,y))
    def expire(self,t):
        for key in list(self.active):
            if t-self.active[key][-1][0]>3:self.flush(key)
    def finish(self):
        for key in list(self.active):self.flush(key)
        return self.finished
