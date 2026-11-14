"""Four schematic through-movement indicators; never infer a controller mapping."""
import json,time
from .signals import apply_change

MOVEMENTS={'N':'SN','S':'NS','E':'WE','W':'EW'}

def retain_signal_events(db,records):
    db.execute("CREATE TABLE IF NOT EXISTS live_signal_state (site TEXT PRIMARY KEY,payload TEXT NOT NULL)")
    states={}
    for r in records:
        site=r['site'];stamp=r['received_at']
        if site not in states:
            row=db.execute('SELECT payload FROM live_signal_state WHERE site=?',(site,)).fetchone()
            states[site]=json.loads(row[0]) if row else {}
        state=states[site]
        if stamp<state.get('last_receipt',0):continue
        if state.get('session')!=r['session'] or stamp-state.get('last_receipt',stamp)>5:
            state.clear();state.update(session=r['session'],phases={},initialized=False)
        change=r['event'].get('phaseChange')
        if isinstance(change,dict):apply_change(state,r['session'],change,stamp,r['event'].get('timestamp'))
        state['last_receipt']=stamp
    for site,state in states.items():db.execute('INSERT OR REPLACE INTO live_signal_state VALUES(?,?)',(site,json.dumps(state)))

def directional_snapshot(store,site,mapping,now=None):
    now=time.time() if now is None else now
    with store.connect() as db:
        exists=db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='live_signal_state'").fetchone()
        row=db.execute('SELECT payload FROM live_signal_state WHERE site=?',(site['id'],)).fetchone() if exists else None
    state=json.loads(row[0]) if row else {};health=store.health(site['id'])
    fresh=0<=now-state.get('last_receipt',0)<=5 and health.get('session')==state.get('session')
    directions=[]
    for direction,movement in MOVEMENTS.items():
        assignment=mapping.get('directions',{}).get(direction,{})
        numbers=assignment.get('phase_numbers',[])
        reason='Movement-to-phase mapping unverified';colour='UNKNOWN'
        if assignment.get('verified') is True and assignment.get('movement')==movement and numbers and assignment.get('evidence'):
            if not fresh:reason='Signal stream stale or unavailable'
            elif not state.get('initialized'):reason='Waiting for absolute phase snapshot'
            else:
                phases=[state.get('phases',{}).get(str(n)) for n in numbers]
                if any(p is None or not 0<=now-p['received_at']<=180 for p in phases):reason='Required phase missing or older than 180 seconds'
                else:
                    colours={p['status'] for p in phases}
                    if len(colours)==1 and next(iter(colours)) in {'GREEN','YELLOW','RED'}:
                        colour=next(iter(colours));reason='Verified through-movement mapping; received API state'
                    else:reason='Assigned phases disagree or are invalid'
        directions.append(dict(direction=direction,movement=movement,status=colour,reason=reason,phase_numbers=numbers))
    lookup={d['direction']:d['status'] for d in directions};checks=[]
    if any(lookup[d]=='GREEN' for d in 'NS') and any(lookup[d]=='GREEN' for d in 'EW'):checks.append('Perpendicular through indicators green: review mapping and controller plan')
    for a,b in [('N','S'),('E','W')]:
        if lookup[a]!='UNKNOWN' and lookup[b]!='UNKNOWN' and lookup[a]!=lookup[b]:checks.append(f'{a}/{b} differ; not automatically an error (signal plans may serve directions separately)')
    return dict(site=site['id'],directions=directions,checks=checks,stream_receiving=fresh,
        vehicle_consistency='Not validated: verified stop lines, movement mapping and synchronized clocks required',
        placement='Schematic cardinal indicators, not surveyed physical signal heads',absolute_received=bool(state.get('initialized')))
