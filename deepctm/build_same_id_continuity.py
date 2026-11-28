"""Publish a derived model revision without rewriting a frozen recording."""
import argparse
import hashlib
import json
from pathlib import Path
import re
from .same_id_continuity import apply
from .validate_same_id_continuity import validate

ROOT=Path(__file__).resolve().parents[1]


def build(capture_id):
    if not re.fullmatch(r'\d{8}T\d{6}Z',capture_id):raise ValueError('Invalid capture ID')
    source=ROOT/'data/frozen/florida'/capture_id
    manifest=json.loads((source/'manifest.json').read_text());inputs={};hashes={}
    for name in ('snapshot.json','reconstruction.json'):
        raw=(source/name).read_bytes();hashes[name]=hashlib.sha256(raw).hexdigest()
        if hashes[name]!=manifest['checksums'][name]:raise ValueError('Frozen input changed')
        inputs[name]=json.loads(raw)
    snapshot=inputs['snapshot.json'];result=apply(snapshot,inputs['reconstruction.json'])
    validation=validate(snapshot);validation['snapshot_sha256']=hashes['snapshot.json']
    result['same_id_continuity']['validation']={k:v for k,v in validation.items() if k!='cases'}
    out=ROOT/'data/reconstruction/frozen'/capture_id;out.mkdir(parents=True,exist_ok=True)
    (out/'same-id-validation.json').write_text(json.dumps(validation,allow_nan=False))
    temp=out/'same-id.tmp'
    temp.write_text(json.dumps(dict(base_hashes=hashes,layers=result),allow_nan=False))
    temp.replace(out/'same-id.json')
    print(json.dumps(dict(capture=capture_id,added=result['same_id_continuity']['added'],
        timing_uncertain=result['same_id_continuity']['timing_uncertain'],
        unresolved=result['same_id_continuity']['unresolved'],validation=validation['pooled'])))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--capture',required=True);build(p.parse_args().capture)
