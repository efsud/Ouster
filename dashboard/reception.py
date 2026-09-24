"""Normalize SDK event clocks without silently inventing a timezone."""
from datetime import datetime
import math

def normalize_event(site,session,event,received_at):
    stamp=event.get('frame',{}).get('timestamp') or event.get('timestamp')
    record=dict(site=site,session=session,event=event,received_at=received_at,source='sdk',sensor_time=None,status='quarantined',reason='missing_timestamp')
    if not isinstance(stamp,str) or not stamp:return record
    try:
        parsed=datetime.fromisoformat(stamp.replace('Z','+00:00'))
        if parsed.tzinfo is None:
            record['reason']='unknown_timezone';return record
        value=parsed.timestamp()
        if not math.isfinite(value):raise ValueError()
        record.update(sensor_time=value,status='received',reason=None)
        if value>received_at+5:record.update(status='quarantined',reason='future_timestamp')
    except (ValueError,OverflowError):record['reason']='invalid_timestamp'
    return record
