"""Read-only SDK recorder with observable errors and durable batch writes."""
import argparse
import getpass
import os
import queue
import time
import uuid
import sqlite3
from pathlib import Path
from .storage import Store
from .reception import normalize_event

def persist_observations(db, batch, record_until):
    archive=[r for r in batch if record_until is None or r['received_at']<record_until]
    preview=[r for r in batch if record_until is not None and r['received_at']>=record_until]
    saved=db.save_batch(archive) if archive else 0
    if preview:db.save_preview(preview)
    return saved

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--site',required=True)
    parser.add_argument('--record-duration',type=int,default=None,help='Raw history seconds; 0 is live-only, omitted is unlimited. Streaming continues.')
    args=parser.parse_args()
    if args.record_duration is not None and args.record_duration<0:parser.error('Record duration must be nonnegative')
    from .sdk_client import ObservableConnection
    from google.protobuf.json_format import MessageToDict
    username=os.getenv('BLUECITY_USERNAME') or input('BlueCity username: ')
    password=os.getenv('BLUECITY_PASSWORD') or getpass.getpass('BlueCity password: ')
    path=os.getenv('OUSTER_DB',str(Path(__file__).resolve().parent.parent/'data/ouster.sqlite3'))
    db=Store(path);session=uuid.uuid4().hex
    record_until=time.time()+args.record_duration if args.record_duration is not None else None
    db.set_health(args.site,state='starting',session=session,error=None,received_count=0,saved_count=0,last_receipt=None,last_sensor_time=None)
    batch=[];last_flush=time.monotonic();last_retention=0;received=0;saved=0;stream=None
    def flush():
        nonlocal saved,last_flush
        if batch:
            saved+=persist_observations(db,batch,record_until);last=batch[-1]
            db.set_health(args.site,state='receiving' if last['status']=='received' else 'timestamp_error',last_receipt=last['received_at'],last_sensor_time=last['sensor_time'],error=last['reason'],received_count=received,saved_count=saved,recording_mode='recording' if record_until is None or last['received_at']<record_until else 'live_only',record_until=record_until)
            batch.clear()
        last_flush=time.monotonic()
    try:
        stream=ObservableConnection(UDID=args.site,username=username,password=password,singleton=True,store_path=path,site_id=args.site,
            subscriptions=[ObservableConnection.subscriptionOption.FRAME,ObservableConnection.subscriptionOption.PHASE_CHANGE,ObservableConnection.subscriptionOption.LOOP_CHANGE],semantic_abs=False)
        while True:
            try:
                # SDK 3.1.0 getter blocks indefinitely; its singleton queue permits a timeout.
                message=stream.queue.get(timeout=.25)
                event=MessageToDict(message);received+=1
                batch.append(normalize_event(args.site,session,event,time.time()))
            except queue.Empty:pass
            if len(batch)>=100 or time.monotonic()-last_flush>=.25:flush()
            if time.time()-last_retention>=3600:
                db.purge_raw();last_retention=time.time()
            if not stream.p.is_alive():
                db.set_health(args.site,state='stopped',error='sdk_process_exited');break
    except KeyboardInterrupt:
        flush();db.set_health(args.site,state='stopped',error=None)
    except sqlite3.Error:
        print(f'{args.site}: storage failure; recorder stopped. Check disk capacity and database access.',flush=True)
        raise SystemExit(1)
    except Exception as exc:
        db.set_health(args.site,state='stopped',error='collector_'+type(exc).__name__)
        print(f'{args.site}: recorder stopped; see collection health.',flush=True)
    finally:
        if stream is not None and stream.p.is_alive():stream.p.terminate();stream.p.join(timeout=5)

if __name__=='__main__':main()
