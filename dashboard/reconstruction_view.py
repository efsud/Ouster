"""Read-only, expiring Florida reconstruction output; no scientific dependencies."""
import json,time
from pathlib import Path
FOLDER=Path(__file__).resolve().parents[1]/'data/reconstruction/word-v1-collection'

def read(now=None,folder=FOLDER):
    now=time.time() if now is None else now
    try:status=json.loads((folder/'status.json').read_text())
    except (OSError,ValueError):return {'state':'waiting','message':'Waiting for the Florida reconstruction study.'}
    safe={k:status[k] for k in ('state','updated_at','readiness','selected_method','test','uncertainty','last_result') if k in status}
    safe['study_age_s']=max(0,now-status.get('updated_at',0))
    try:layers=json.loads((folder/'layers.json').read_text())
    except (OSError,ValueError):return {'state':'waiting','study':safe,'message':'Collecting or evaluating fixed training/validation/test portions. Estimates are not available yet.'}
    if layers['expires_at']<now:return {'state':'expired','study':safe,'message':'Estimated layer expired; awaiting the current recorded window.'}
    try:later=json.loads((folder/'later-evaluation.json').read_text())
    except (OSError,ValueError):later=None
    try:association=json.loads((folder/'association-20261121.json').read_text())
    except (OSError,ValueError):association=None
    if association is not None:
        association={k:association[k] for k in ('state','selected_method','test','limitations','deployment') if k in association}
    return {**layers,'study':safe,'later_validation':later,'association_validation':association}
