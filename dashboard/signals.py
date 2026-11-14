"""Read-only reconstruction of recorded signal changes, with explicit completeness."""
import json
import threading
import time
from datetime import datetime

STATUS={0:'INVALID',1:'GREEN',2:'YELLOW',3:'RED'}

def apply_change(state,session,change,receipt,event_timestamp=None):
    if state.get('session')!=session:
        state.clear();state.update(session=session,phases={},initialized=False)
    if change.get('absolute') is True:
        state['phases']={};state['initialized']=True
    for phase in change.get('phases',[]):
        if not isinstance(phase,dict) or phase.get('phaseNumber') is None:continue
        number=str(phase['phaseNumber']);code=phase.get('status',0)
        stamp=phase.get('timestamp') or event_timestamp
        old=state['phases'].get(number)
        try:
            if old and stamp and old['sensor_timestamp'] and datetime.fromisoformat(stamp)<datetime.fromisoformat(old['sensor_timestamp']):continue
        except (ValueError,TypeError):pass
        state['phases'][number]={'phase':number,'status':STATUS.get(code,'UNKNOWN'),'code':code,'sensor_timestamp':stamp,'received_at':receipt}
    state['last_change_receipt']=receipt

class SignalReader:
    def __init__(self,store):
        self.store=store;self.cache={};self.lock=threading.Lock()

    def snapshot(self,site,now=None):
        now=time.time() if now is None else now
        with self.lock:
            entry=self.cache.setdefault(site,{'cursor':0,'since':now-600,'state':{},'last_event':None})
            with self.store.connect() as db:
                rows=db.execute('SELECT sequence,session,received_at,json_extract(payload,\'$.phaseChange\') change,json_extract(payload,\'$.timestamp\') stamp FROM raw_events INDEXED BY raw_site_receipt WHERE site=? AND received_at>=? AND sequence>? ORDER BY received_at,sequence LIMIT 20000',(site,entry['since'],entry['cursor'])).fetchall()
            for r in rows:
                state=entry['state']
                # Gaps invalidate the reconstructed snapshot; never carry a green through an outage.
                if state.get('session')!=r['session'] or (entry['last_event'] is not None and r['received_at']-entry['last_event']>5):
                    state.clear();state.update(session=r['session'],phases={},initialized=False)
                entry['last_event']=r['received_at'];entry['cursor']=r['sequence'];entry['since']=r['received_at']
                if r['change'] is not None:apply_change(state,r['session'],json.loads(r['change']),r['received_at'],r['stamp'])
            state=entry['state'];health=self.store.health(site)
            recent=entry['last_event'] is not None and 0<=now-entry['last_event']<=5
            connected=recent and health.get('session')==state.get('session') and health.get('state') not in ['stopped','authentication_failed','routing_failed']
            phases=[]
            for p in state.get('phases',{}).values():
                age=max(0,now-p['received_at']);current=connected and state.get('initialized',False) and age<=180
                phases.append(dict(p,age_s=age,display_status=p['status'] if current else 'UNCONFIRMED'))
            phases.sort(key=lambda p:(not p['phase'].isdigit(),int(p['phase']) if p['phase'].isdigit() else p['phase']))
            return dict(site=site,phases=phases,stream_receiving=connected,absolute_received=state.get('initialized',False),
                        last_change_receipt=state.get('last_change_receipt'),error=health.get('error'),
                        note='Phase numbers are not mapped to movements. Sensor timezone is unverified. Reconstruction starts with the last 10 minutes of saved events; no absolute snapshot means partial state. States older than 180 seconds are unconfirmed, even if object frames continue.')
