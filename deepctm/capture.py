"""24-hour compressed read-only capture. Credentials are only in process memory."""
import argparse
import getpass
import gzip
import json
import os
from pathlib import Path
import queue
import shutil
import signal
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]

def atomic(path, data):
    path=Path(path); tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(data,indent=2,allow_nan=False)); tmp.replace(path)

def worker(site, directory, deadline):
    from dashboard.sdk_client import ObservableConnection
    from google.protobuf.json_format import MessageToDict
    from dashboard.storage import Store
    directory=Path(directory); session=uuid.uuid4().hex
    health=directory/(site+'-status.json'); stream=None; output=None; bucket=None
    state={'site':site,'session':session,'events':0,'frames':0,'last_receipt':None,'state':'connecting'}
    atomic(health,state)
    # SDK needs a tiny status DB; raw events are compressed separately.
    Store(directory/(site+'-health.sqlite3'))
    try:
        stream=ObservableConnection(UDID=site,username=os.environ['BLUECITY_USERNAME'],password=os.environ['BLUECITY_PASSWORD'],singleton=True,
            store_path=str(directory/(site+'-health.sqlite3')),site_id=site,
            subscriptions=[ObservableConnection.subscriptionOption.FRAME,ObservableConnection.subscriptionOption.PHASE_CHANGE,ObservableConnection.subscriptionOption.LOOP_CHANGE],semantic_abs=False)
        last_flush=time.monotonic()
        while time.time()<deadline:
            if shutil.disk_usage(directory).free<2*1024**3:raise RuntimeError('insufficient_disk_space')
            try:message=stream.queue.get(timeout=.25)
            except queue.Empty:
                if not stream.p.is_alive():raise RuntimeError('sdk_process_exited')
                continue
            received=time.time()
            if received>=deadline:break
            event=MessageToDict(message);hour=int(received//3600)
            if hour!=bucket:
                if output:output.close()
                output=gzip.open(directory/f'{site}-{hour}-{session}.jsonl.gz','at',encoding='utf-8');bucket=hour
            output.write(json.dumps({'site':site,'session':session,'received_at':received,'payload':event},separators=(',',':'))+'\n')
            state.update(state='receiving',last_receipt=received,events=state['events']+1,frames=state['frames']+int('frame' in event))
            if time.monotonic()-last_flush>=1:
                output.flush();atomic(health,state);last_flush=time.monotonic()
        state['state']='complete'
    except KeyboardInterrupt:state['state']='interrupted'
    except Exception as exc:
        state.update(state='failed',error=type(exc).__name__) # Never serialize SDK exception text.
    finally:
        if output:output.close()
        if stream is not None and stream.p.is_alive():stream.p.terminate();stream.p.join(timeout=5)
        atomic(health,state)

def stop(p):
    if p.poll() is None:
        os.killpg(p.pid,signal.SIGINT)
        try:p.wait(timeout=10)
        except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()

def main():
    p=argparse.ArgumentParser();p.add_argument('--worker');p.add_argument('--directory');p.add_argument('--deadline',type=float);p.add_argument('--seconds',type=int,default=86400);p.add_argument('--record-only',action='store_true',help='Save observations without starting model training')
    a=p.parse_args()
    if a.worker:return worker(a.worker,a.directory,a.deadline)
    if not sys.stdin.isatty():raise SystemExit('Use the private Terminal launcher.')
    if not 60<=a.seconds<=86400:raise SystemExit('Duration must be 60–86400 seconds.')
    config=json.loads((ROOT/'config/deepctm.json').read_text())
    print(f'Read-only Weston + Signet capture. Leave this Terminal open for {a.seconds/3600:g} hour(s).')
    username=input('BlueCity API username: ').strip();password=getpass.getpass('BlueCity password (hidden): ')
    if not username or not password:raise SystemExit('Credentials required.')
    now=time.time();directory=ROOT/'data/deepctm'/time.strftime('%Y%m%dT%H%M%SZ',time.gmtime(now));directory.mkdir(parents=True)
    atomic(directory/'config.json',config)
    manifest={'state':'recording','start':now,'end':now+a.seconds,'sites':config['sites_west_to_east'],'directory':str(directory),'restarts':{},'format':'gzip JSONL, receipt timestamps + original SDK payload'}
    atomic(directory/'manifest.json',manifest);atomic(ROOT/'data/deepctm/latest.json',{'directory':str(directory)})
    env=dict(os.environ,BLUECITY_USERNAME=username,BLUECITY_PASSWORD=password)
    children={}; launched={};awake=None;complete=False
    def launch(site):
        children[site]=subprocess.Popen([sys.executable,'-m','deepctm.capture','--worker',site,'--directory',str(directory),'--deadline',str(manifest['end'])],cwd=ROOT,env=env,start_new_session=True)
        launched[site]=time.time()
    try:
        if sys.platform=='darwin':awake=subprocess.Popen(['caffeinate','-i','-w',str(os.getpid())])
        for site in manifest['sites']:launch(site)
        print(f'Capture folder: {directory}',flush=True)
        while time.time()<manifest['end']:
            if shutil.disk_usage(directory).free<2*1024**3:raise RuntimeError('Disk free space below 2 GiB')
            for site,child in list(children.items()):
                status_path=directory/(site+'-status.json')
                status=json.loads(status_path.read_text()) if status_path.exists() else {}
                if time.time()-launched[site]>90 and (child.poll() is not None or time.time()-max(launched[site],status.get('last_receipt') or 0)>60):
                    count=manifest['restarts'].get(site,0)
                    if count>=10:raise RuntimeError('Repeated reception failure: '+site)
                    stop(child);manifest['restarts'][site]=count+1;atomic(directory/'manifest.json',manifest);launch(site)
            time.sleep(1)
        complete=True;manifest['state']='captured'
    except KeyboardInterrupt:manifest.update(state='interrupted',error='Stopped by user')
    except Exception as exc:manifest.update(state='failed',error=str(exc))
    finally:
        for child in children.values():stop(child)
        if awake:awake.terminate()
        manifest['finished_at']=time.time();atomic(directory/'manifest.json',manifest)
    if complete and not a.record_only:
        # Training has no credentials, network access, or SDK dependency.
        command=[str(ROOT/'.venv-deepctm/bin/python'),'-m','deepctm.experiment','--capture',str(directory)]
        outcome=subprocess.run(command,cwd=ROOT)
        manifest['state']='experiment_complete' if outcome.returncode==0 else 'analysis_failed'
        atomic(directory/'manifest.json',manifest)
    print('Capture status:',manifest['state'],flush=True)

if __name__=='__main__':main()
