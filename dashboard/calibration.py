"""Validate local map calibration against independently located landmarks."""
import math
from .analytics import local_to_geo, finite

def report(site):
    reasons=[];errors=[];origin=site.get('origin',{});cal=site.get('calibration',{})
    if site.get('calibration_verified') is not True:reasons.append('Calibration not verified')
    if not cal.get('version'):reasons.append('Calibration version missing')
    if not cal.get('reference'):reasons.append('Authoritative reference missing')
    points=cal.get('landmarks',[])
    if len(points)<3:reasons.append('At least three independent landmarks required')
    try:
        threshold=finite(cal.get('max_residual_m',2),'max_residual_m',.01)
        local_to_geo(0,0,origin['lat'],origin['lng'],site['rotation_deg'])
        for p in points:
            lat,lng=local_to_geo(p['x'],p['y'],origin['lat'],origin['lng'],site['rotation_deg'])
            finite(p['lat'],'landmark latitude');finite(p['lng'],'landmark longitude')
            north=math.radians(lat-p['lat'])*6378137
            east=math.radians(lng-p['lng'])*6378137*math.cos(math.radians(origin['lat']))
            errors.append(math.hypot(east,north))
        if errors and max(errors)>threshold:reasons.append('Landmark residual exceeds tolerance')
        if len({(p['x'],p['y']) for p in points})<3:reasons.append('Landmarks must be distinct')
    except (KeyError,ValueError,TypeError):reasons.append('Invalid origin, rotation or landmarks')
    return {'valid':not reasons,'version':cal.get('version'),'reference':cal.get('reference'),'residuals_m':errors,'max_residual_m':max(errors) if errors else None,'reasons':reasons}
