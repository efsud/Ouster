"""Read explicitly retained study snapshots, separate from expiring live data."""
import hashlib
import json
from pathlib import Path
import re

FOLDER=Path(__file__).resolve().parents[1]/'data/frozen/florida'
DERIVED=Path(__file__).resolve().parents[1]/'data/reconstruction/frozen'


def read(capture_id, reconstruction=False, folder=FOLDER, derived_folder=DERIVED):
    if not isinstance(capture_id,str) or not re.fullmatch(r'\d{8}T\d{6}Z',capture_id):
        raise ValueError('Invalid frozen capture ID')
    base=Path(folder).resolve();capture=(base/capture_id).resolve()
    if capture.parent!=base:
        raise ValueError('Invalid frozen capture location')
    def file(name):
        path=(capture/name).resolve()
        if path.parent!=capture:
            raise ValueError('Invalid frozen capture asset')
        return path
    try:
        manifest=json.loads(file('manifest.json').read_text())
        if manifest.get('state')!='frozen':
            return {'state':'waiting','message':'This frozen study hour is still being verified.'}
        name='reconstruction.json' if reconstruction else 'snapshot.json'
        raw=file(name).read_bytes()
        expected=manifest.get('checksums',{}).get(name)
        if not expected or hashlib.sha256(raw).hexdigest()!=expected:
            raise ValueError('Frozen capture integrity check failed')
        value=json.loads(raw)
    except FileNotFoundError:
        return {'state':'unavailable','message':'Frozen study data is unavailable.'}
    if (value.get('start')!=manifest['start'] or value.get('end')!=manifest['end'] or
        (reconstruction and value.get('snapshot_generated_at')!=manifest['end'])):
        raise ValueError('Frozen study window does not match its manifest')
    if reconstruction:
        # Model outputs live outside the sealed archive. Require the exact input
        # hashes, not just an overlapping time window, before showing a revision.
        derived_root=Path(derived_folder).resolve()
        derived=(derived_root/capture_id/'same-id.json').resolve()
        if not derived.is_relative_to(derived_root) or derived.parent.name!=capture_id:
            raise ValueError('Invalid frozen derived location')
        if derived.exists():
            revision=json.loads(derived.read_text())
            if any(revision.get('base_hashes',{}).get(name)!=manifest['checksums'].get(name)
                   for name in ('snapshot.json','reconstruction.json')):
                raise ValueError('Derived layer does not match frozen inputs')
            updated=revision['layers']
            if (updated.get('start'),updated.get('end'),updated.get('snapshot_generated_at'))!=(manifest['start'],manifest['end'],manifest['end']):
                raise ValueError('Derived layer window mismatch')
            value=updated
    # This explicit archive endpoint has no rolling expiry. The original
    # rolling endpoints retain their existing 90-minute expiration policy.
    value.update(state='ready',frozen=True,capture_id=capture_id,
                 archive_created_at=manifest['created_at'],expires_at=None)
    if not reconstruction:
        value.update(next_update=None,version=expected,
                     estimates={'method':'Recorded study data; separate inferred layers','links':[]})
    return value
