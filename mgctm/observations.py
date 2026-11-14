"""Report Florida recording eligibility without interpreting raw messages as traffic."""
from datetime import datetime
import json
from pathlib import Path
from zoneinfo import ZoneInfo


def archive_audit(root):
    root=Path(root)
    result=[]
    for manifest in sorted(root.glob('*/manifest.json')):
        m=json.loads(manifest.read_text())
        index=manifest.parent/'observed/index.json'
        if not index.exists():
            result.append(dict(capture=manifest.parent.name,state=m['state'],processed=False))
            continue
        report=json.loads(index.read_text())
        eastern=ZoneInfo('America/New_York')
        start=datetime.fromtimestamp(m['start'],eastern)
        result.append(dict(capture=manifest.parent.name,state=m['state'],processed=True,
            start=start.isoformat(),end=datetime.fromtimestamp(m['end'],eastern).isoformat(),
            sites=[dict(site=s['id'],frames=s['frames'],gaps_over_3s=s['gaps_over_3s'],
                        car_detections=s['object_classes'].get('2',0),
                        projected=s['calibrated_projection']) for s in report['sites']]))
    return dict(archives=result,field_fit_ready=False,
        missing=['verified lane groups, bay split points and detector-to-cell mapping',
                 'aligned controller phase-to-movement records and turn/boundary series',
                 'independent dated passenger-car counts and queue/spillback observations'])
