"""Local maintenance and automatic processing of verified sites."""
import threading
import time
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
from .processing import process_range,validate_scene,calendar_bounds
from .anomalies import evaluate_health,evaluate_traffic

def start_worker(store,site_provider):
    stop=threading.Event()
    def run():
        next_processing=0;next_purge=0
        while not stop.is_set():
            now=time.time()
            try:
                entries=site_provider()
                for site in entries:evaluate_health(store,site,now)
                if now>=next_purge:store.purge_raw(now);next_purge=now+3600
                if now>=next_processing:
                    next_processing=now+60
                    for site in entries:
                        try:
                            validate_scene(site)
                        except (ValueError,KeyError,TypeError) as exc:
                            store.set_health(site['id'],processing_state='blocked_metadata',processing_reason=str(exc));continue
                        availability=store.availability(site['id'])
                        if availability['first'] is None:continue
                        last_closed=int(min(now-300,availability['last']-300)//300)*300
                        with store.connect() as db:
                            done=db.execute("SELECT max(end) FROM windows WHERE site=? AND source='sdk-derived' AND end-start=300",(site['id'],)).fetchone()[0]
                        begin=max(int(availability['first']//300)*300,done or 0,store.health(site['id']).get('processing_cursor',0))
                        finish=min(begin+600,last_closed)
                        if finish>begin:
                            try:
                                process_range(store,site,begin,finish)
                                store.set_health(site['id'],processing_state='ready',processing_reason=None,processing_cursor=finish)
                                evaluate_traffic(store,site)
                            except ValueError as exc:
                                if str(exc)=='No valid received frames in this interval':
                                    store.set_health(site['id'],processing_state='waiting_observations',processing_reason=str(exc),processing_cursor=finish)
                                else:raise
                        zone=site.get('timezone','America/Toronto');yesterday=(datetime.fromtimestamp(now,ZoneInfo(zone)).date()-timedelta(days=1)).isoformat()
                        a,b=calendar_bounds(yesterday,zone)
                        with store.connect() as db:
                            exists=db.execute("SELECT 1 FROM windows WHERE site=? AND source='sdk-derived' AND start=? AND end=? LIMIT 1",(site['id'],a,b)).fetchone()
                        if not exists and availability['first']<=a and availability['last']>=b+300:
                            process_range(store,site,a,b,'daily')
            except Exception as exc:
                # No credentials or raw response text in worker output.
                print('Maintenance deferred: '+type(exc).__name__,flush=True)
            stop.wait(1)
    thread=threading.Thread(target=run,name='ouster-maintenance',daemon=True);thread.start()
    return stop
