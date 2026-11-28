"""Version the actual display transforms separately from numerical models."""
import hashlib,json

def manifest(sites):
    entries={s['id']:{'origin':s['reference_location'],
        'rotation_deg':s.get('preview_rotation_deg',220),
        'mirror_y':bool(s.get('preview_mirror_y',False)),
        'alignment_version':s.get('preview_alignment_version','unspecified')} for s in sites}
    # Origins include provenance so a changed accuracy claim is traceable too.
    digest=hashlib.sha256(json.dumps(entries,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return {'sha256':digest,'sites':entries,'accuracy':'provisional; not surveyed calibration'}
