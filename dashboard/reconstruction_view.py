"""Read-only, expiring Florida reconstruction output; no scientific dependencies."""
import json,time
from pathlib import Path
FOLDER=Path(__file__).resolve().parents[1]/'data/reconstruction/word-v1-collection'

def read(now=None,folder=FOLDER):
    now=time.time() if now is None else now
    try:status=json.loads((folder/'status.json').read_text())
    except (OSError,ValueError):return {'state':'waiting','message':'Waiting for the corridor reconstruction study.'}
    safe={k:status[k] for k in ('state','updated_at','readiness','selected_method','test','uncertainty','last_result') if k in status}
    safe['study_age_s']=max(0,now-status.get('updated_at',0))
    try:layers=json.loads((folder/'layers.json').read_text())
    except (OSError,ValueError):return {'state':'waiting','study':safe,'message':'Collecting or evaluating fixed training/validation/test portions. Estimates are not available yet.'}
    if layers['expires_at']<now:return {'state':'expired','study':safe,'message':'Estimated layer expired; awaiting the current recorded window.'}
    if layers.get('method')=='color_slope_chronological_v1':
        # This baseline has its own compact validation; do not load unrelated
        # archived studies or label their results as evidence for this method.
        return {**layers,'study':safe}
    try:later=json.loads((folder/'later-evaluation.json').read_text())
    except (OSError,ValueError):later=None
    try:association=json.loads((folder/'association-20261121.json').read_text())
    except (OSError,ValueError):association=None
    if association is not None:
        association={k:association[k] for k in ('state','selected_method','test','limitations','deployment') if k in association}
    try:integration=json.loads((folder/'integrated-validation.json').read_text())
    except (OSError,ValueError):integration=None
    try:archive=json.loads((folder.parent/'archive-extension/evaluation/report.json').read_text())
    except (OSError,ValueError):archive=None
    if archive and archive.get('state')!='complete':archive=None
    try:endpoint=json.loads((folder.parent/'endpoint-speed/evaluation/report.json').read_text())
    except (OSError,ValueError):endpoint=None
    if endpoint and endpoint.get('state')!='complete':endpoint=None
    try:all_sites=json.loads((folder.parent/'all-florida/pair-audit.json').read_text()).get('site_validation',[])
    except (OSError,ValueError):all_sites=[]
    if folder.name=='finch':archive=None;endpoint=None;all_sites=[]
    campaign=None
    try:
        c=json.loads((folder.parent/'eight-hour-20261123/status.json').read_text())
        region='finch' if folder.name=='finch' else 'florida'
        campaign={k:c.get(k) for k in ('state','started_at','deadline','updated_at')}
        campaign['region']=c.get('regions',{}).get(region,{})
        campaign['cumulative']=c.get('cumulative',{}).get(region,{})
    except (OSError,ValueError):pass
    bidirectional=None
    if layers.get('association_method')=='bidirectional_shape_v1':
        try:
            evidence=json.loads((folder.parent/'bidirectional-review/report.json').read_text())
            bidirectional={k:evidence[k] for k in ('state','test','limitations','deployment_eligible')}
        except (OSError,ValueError,KeyError):pass
    pair_diagnostics=[]
    for link in layers.get('association_diagnostics',[]):
        displayed=sum(p['sites']==link['sites'] and p['direction']==link['direction'] for p in layers.get('between_intersections',[]))
        pair_diagnostics.append({**link,'displayed_matches':displayed,'final_rejections':link['proposed_matches']-displayed})
    return {**layers,'bidirectional_validation':bidirectional,'campaign':campaign,'all_site_validation':all_sites,'pair_diagnostics':pair_diagnostics,'endpoint_validation':endpoint,'archive_validation':archive,'study':safe,'later_validation':later,'association_validation':association,'integration_validation':integration}
