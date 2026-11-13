"""OSM evidence inventory and cell export. Audits are never simulation inputs."""
import csv
import json
import math
from pathlib import Path
from urllib.parse import urlparse

TAGS = ('name','highway','lanes','lanes:forward','lanes:backward','turn:lanes',
        'turn:lanes:forward','turn:lanes:backward','maxspeed','oneway','access','service')


def write_csv(path, rows, fields=None):
    rows=list(rows)
    if not rows and not fields:
        raise ValueError('An empty table needs a declared schema')
    with Path(path).open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields or list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def download(study, out):
    import osmnx as ox
    import requests
    out=Path(out)
    out.mkdir(parents=True,exist_ok=True)
    ox.settings.useful_tags_way=list(dict.fromkeys([*ox.settings.useful_tags_way,*TAGS]))
    ox.settings.useful_tags_node=list(dict.fromkeys([*ox.settings.useful_tags_node,'highway','traffic_signals:direction','access']))
    ox.settings.cache_folder=out/'osm-cache'
    ox.settings.requests_timeout=45
    west,south,east,north=study['bbox_wsen']
    graph=ox.graph_from_bbox((west,south,east,north),network_type='drive_service',
                            simplify=False,retain_all=True)
    ox.save_graphml(graph,filepath=out/'directed.graphml')
    nodes,edges=ox.graph_to_gdfs(graph)
    edges.reset_index().to_file(out/'directed.geojson',driver='GeoJSON')
    signals=nodes[nodes['highway'].astype(str).str.contains('traffic_signals',na=False)] if 'highway' in nodes else nodes.iloc[:0]
    (out/'signals.geojson').write_text(signals.reset_index().to_json())
    # OSMnx graph topology does not enforce restriction relations. Preserve
    # raw relation membership for manual mapping; never infer turn permission.
    url=ox.settings.overpass_url.rstrip('/')+'/interpreter'
    if urlparse(url).scheme!='https':
        raise ValueError('Overpass endpoint must use HTTPS')
    query=f'[out:json][timeout:40];relation["type"="restriction"]({south},{west},{north},{east});out body;'
    restriction_status='downloaded; manual mapping required'
    try:
        response=requests.post(url,data={'data':query},timeout=50)
        response.raise_for_status()
        relation_data=response.json()
        if 'elements' not in relation_data or relation_data.get('remark'):
            raise ValueError('Incomplete restriction response')
        (out/'turn-restrictions.json').write_text(json.dumps(relation_data,indent=2))
    except (requests.RequestException,ValueError) as exc:
        code=getattr(getattr(exc,'response',None),'status_code',None)
        restriction_status=f'unavailable ({code or type(exc).__name__}); cannot infer permitted turns'
    rows=[]
    for u,v,k,a in graph.edges(keys=True,data=True):
        rows.append(dict(u=u,v=v,key=k,osm_way=a.get('osmid'),length_m=a.get('length'),
                         **{tag:a.get(tag,'') for tag in TAGS},
                         verified_lane_ids='',verified_turns='',bay_start_m='',stop_line_m='',
                         verified_source='',status='unverified'))
    write_csv(out/'geometry-review.csv',rows)
    audit=dict(study=study['name'],bbox=study['bbox_wsen'],source='© OpenStreetMap contributors, ODbL',
               directed_edges=len(rows),signal_nodes=len(signals),restrictions=restriction_status,
               gaps={tag:sum(not row[tag] for row in rows) for tag in ('lanes','turn:lanes','maxspeed')},
               model_ready=False)
    (out/'audit.json').write_text(json.dumps(audit,indent=2))
    return audit


def cutline(points,start,end):
    """Slice a polyline by normalized arclength."""
    lengths=[math.dist(p,q) for p,q in zip(points,points[1:])]
    total=sum(lengths)
    first,last=start*total,end*total
    result=[]; p0=0.
    for (a,b),length in zip(zip(points,points[1:]),lengths):
        p1=p0+length
        if length and p1>=first and p0<=last:
            for t in (max(first,p0),min(last,p1)):
                xy=[x+(y-x)*(t-p0)/length for x,y in zip(a,b)]
                if not result or math.dist(result[-1],xy)>1e-9:
                    result.append(xy)
        p0=p1
    return result


def export_cells(net,out):
    out=Path(out)
    rows=[]; geom=[]
    upstream=[[] for _ in net.cells];downstream=[[] for _ in net.cells]
    for e in net.edges:
        downstream[e.src].append(net.cells[e.dst].id if e.dst>=0 else 'EXIT')
        if e.dst>=0: upstream[e.dst].append(net.cells[e.src].id)
    for i,c in enumerate(net.cells):
        s=c.section
        row=dict(cell=c.id,link=s.link,section=s.id,movements=''.join(s.turns),
            start_m=c.start_m,end_m=c.end_m,length_m=c.length,lanes=len(s.lanes),
            lane_ids='|'.join(s.lanes),bay=s.bay,storage_vehicles=net.storage[i],
            capacity_veh_s=net.capacity[i],upstream='|'.join(sorted(set(upstream[i]))),
            downstream='|'.join(sorted(set(downstream[i]))))
        dx=s.end_m-s.start_m
        coordinates=cutline(s.xy,(c.start_m-s.start_m)/dx,(c.end_m-s.start_m)/dx)
        rows.append(row)
        geom.append(dict(type='Feature',geometry=dict(type='LineString',coordinates=coordinates),properties=row))
    write_csv(out/'cells.csv',rows)
    # Model geometry uses metric XY, not RFC 7946 geographic coordinates.
    (out/'cell-geometry.json').write_text(json.dumps(dict(coordinate_system='local metric XY',features=geom)))
    return geom
