"""Snapshot provisional map metadata for all Finch sensors; no invented calibration."""
import math

def geometry(positions):
    stations=[0.];bearings=[]
    for a,b in zip(positions,positions[1:]):
        east=(b['lng']-a['lng'])*111320*math.cos(math.radians((a['lat']+b['lat'])/2))
        north=(b['lat']-a['lat'])*111320
        stations.append(stations[-1]+math.hypot(east,north));bearings.append(math.degrees(math.atan2(north,east)))
    local=[bearings[0]]+[math.degrees(math.atan2(math.sin(math.radians(a))+math.sin(math.radians(b)),math.cos(math.radians(a))+math.cos(math.radians(b)))) for a,b in zip(bearings,bearings[1:])]+[bearings[-1]]
    return stations,local

def configuration(sites):
    entries=sorted((s for s in sites if s.get('region')=='Toronto'),key=lambda s:s['reference_location']['lng'])
    if len(entries)!=10:raise ValueError('Expected the ten configured Finch intersections')
    positions=[s['reference_location'] for s in entries];stations,bearings=geometry(positions)
    return {'version':'finch-corridor-recording-1','title':'Finch West corridor · ten intersections','sites_west_to_east':[s['id'] for s in entries],
        'site_names':[s['name'].replace('Finch W & ','').replace(' (LRT)','') for s in entries],
        'site_positions':positions,'station_m':stations,'road_bearings_deg':bearings,'rotation_deg':[s.get('preview_rotation_deg',220) for s in entries],
        'assumptions':['Sensor origins and rotations use existing provisional map alignment, not surveyed calibration.',
            'Station distance is cumulative straight-line separation between ordered sensor origins, not surveyed road length.',
            'Direction is relative to the local corridor bearing; turning movements are not independently verified.',
            'Missing sensor data remains blank; vehicle tracks are never joined between sites.',
            'Speed colors describe movement, not traffic-light states. No model training is run.']}
