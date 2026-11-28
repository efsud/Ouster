"""Attach measured stationary fragments to nearby same-ID direction evidence.

No new positions are created. Conflicting directions or missing nearby evidence
leave a stationary fragment unassigned. This is an experimental build option.
"""
def attach(tracks,max_separation=120):
    moving={}
    for tr in tracks:
        if not tr.get('stationary_context'):
            moving.setdefault(tuple(tr['source_key'][:2]),[]).append(tr)
    out=[]
    for tr in tracks:
        if not tr.get('stationary_context'):out.append(tr);continue
        lo,hi=tr['points'][0][0],tr['points'][-1][0]
        evidence=[]
        for other in moving.get(tuple(tr['source_key'][:2]),[]):
            a,b=other['points'][0][0],other['points'][-1][0]
            if a<=hi and b>=lo:continue
            separation=a-hi if a>hi else lo-b
            if separation<=max_separation:evidence.append(other)
        directions={t['direction'] for t in evidence}
        if len(directions)!=1:continue
        out.append(dict(tr,direction=next(iter(directions)),direction_evidence='nearby_same_sensor_session_object_moving_fragment'))
    return out
