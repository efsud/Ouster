"""Local named-road tangent for trajectory projection, independent of LiDAR rotation.

An inter-sensor chord is not the road direction at an intersection on a bend.
Cached OSM geometry remains provisional, not surveyed lane geometry.
"""
import math
from statistics import median

def nearest_axis(origin,ways,road_name,max_distance=30):
    rows=[]
    def xy(p):return ((p['lon']-origin['lng'])*111320*math.cos(math.radians(origin['lat'])),(p['lat']-origin['lat'])*111320)
    for way in ways:
        if way.get('tags',{}).get('name')!=road_name:continue
        points=way.get('geometry',[])
        for a,b in zip(points,points[1:]):
            ax,ay=xy(a);bx,by=xy(b);dx=bx-ax;dy=by-ay;length=dx*dx+dy*dy
            if length<1:continue
            u=max(0,min(1,-(ax*dx+ay*dy)/length));distance=math.hypot(ax+u*dx,ay+u*dy)
            if distance>max_distance:continue
            angle=(math.degrees(math.atan2(dy,dx))+90)%180-90
            rows.append((distance,angle))
    chosen=sorted(rows)[:4]
    if len(chosen)<2:return None
    # Reject conflicting local segments or wraparound at near-north headings.
    angles=[angle for _,angle in chosen]
    if max(angles)-min(angles)>20:return None
    return {'bearing_deg':median(angles),'road_name':road_name,'segments':len(chosen),'nearest_distance_m':chosen[0][0],
            'source':'cached OpenStreetMap named-road geometry','accuracy':'provisional local tangent, not surveyed'}

def corridor_segments(origin,ways,road_name,bearing_deg,radius=200):
    """Named-road centerlines in the local corridor basis; no side-street widening."""
    angle=math.radians(bearing_deg);c=math.cos(angle);s=math.sin(angle);segments=[]
    def local(p):
        x=(p['lon']-origin['lng'])*111320*math.cos(math.radians(origin['lat']));y=(p['lat']-origin['lat'])*111320
        return [c*x+s*y,-s*x+c*y]
    for way in ways:
        if way.get('tags',{}).get('name')!=road_name:continue
        p=way.get('geometry',[])
        for a,b in zip(p,p[1:]):
            a,b=local(a),local(b)
            if min(math.hypot(*a),math.hypot(*b))<=radius:segments.append([a,b])
    return segments

def road_contains(x,y,segments,half_width=12):
    for (ax,ay),(bx,by) in segments:
        dx=bx-ax;dy=by-ay;length=dx*dx+dy*dy
        if length<1:continue
        u=max(0,min(1,((x-ax)*dx+(y-ay)*dy)/length))
        if math.hypot(x-ax-u*dx,y-ay-u*dy)<=half_width:return True
    return False

def road_distance(a,b,ways,road_name,max_snap=30):
    """Shortest connected named-road centerline distance; no invented connectors."""
    import heapq
    graph={};segments=[]
    lat=math.radians((a['lat']+b['lat'])/2)
    def metric(p,q):return math.hypot((p[0]-q[0])*111320*math.cos(lat),(p[1]-q[1])*111320)
    for way in ways:
        if way.get('tags',{}).get('name')!=road_name:continue
        points=[(p['lon'],p['lat']) for p in way.get('geometry',[])]
        for u,v in zip(points,points[1:]):
            length=metric(u,v)
            if length<.1:continue
            graph.setdefault(u,{})[v]=length;graph.setdefault(v,{})[u]=length;segments.append((u,v,length))
    def snaps(origin):
        rows=[];ox,oy=origin['lng'],origin['lat']
        for u,v,L in segments:
            ax=(u[0]-ox)*111320*math.cos(lat);ay=(u[1]-oy)*111320
            dx=(v[0]-u[0])*111320*math.cos(lat);dy=(v[1]-u[1])*111320
            f=max(0,min(1,-(ax*dx+ay*dy)/(L*L)));d=math.hypot(ax+f*dx,ay+f*dy)
            if d<=max_snap:rows.append((d,u,v,L,f))
        return sorted(rows)[:4]
    starts,ends=snaps(a),snaps(b)
    if not starts or not ends:return None
    options=[]
    for da,u,v,L,f in starts:
        distances={u:f*L,v:(1-f)*L};queue=[(d,node) for node,d in distances.items()];heapq.heapify(queue)
        while queue:
            d,node=heapq.heappop(queue)
            if d>distances[node]:continue
            for neighbor,cost in graph[node].items():
                nd=d+cost
                if nd<distances.get(neighbor,float('inf')):distances[neighbor]=nd;heapq.heappush(queue,(nd,neighbor))
        for db,x,y,K,g in ends:
            length=min(distances.get(x,float('inf'))+g*K,distances.get(y,float('inf'))+(1-g)*K)
            if (u,v)==(x,y):length=min(length,abs(f-g)*L)
            if math.isfinite(length):options.append((length+da+db,length,da,db))
    if not options:return None
    _,length,da,db=min(options)
    return {'distance_m':length,'endpoint_snap_m':[da,db],'source':'connected cached OSM named-road centerline; undirected distance only'}
