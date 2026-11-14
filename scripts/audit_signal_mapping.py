"""Audit recorded phases and stop/release evidence; never infer physical signal heads."""
import argparse,json,math,sqlite3
from collections import defaultdict
from datetime import datetime
from pathlib import Path

VEHICLES={'1','2','3','4','5','6','7','8','9','15'}
def stamp(value):
    try:return datetime.fromisoformat(value)
    except (TypeError,ValueError):return None

def audit(db,site):
    end=db.execute('SELECT max(received_at) FROM raw_events WHERE site=?',(site,)).fetchone()[0]
    if end is None:return {'site':site,'no_data':True}
    start=end-3600;phase_states={};valid=set();invalid=set();vectors=[];greens=defaultdict(list);previous_session=None
    tracks={};releases=[];frame_count=0;absolute_count=0;last_receipt=None;coverage=0
    for row in db.execute('SELECT session,received_at,payload FROM raw_events INDEXED BY raw_site_receipt WHERE site=? AND received_at>=? AND received_at<=? ORDER BY received_at,sequence',(site,start,end)):
        session,receipt,raw=row;e=json.loads(raw);t=stamp(e.get('timestamp'))
        if session!=previous_session or (last_receipt is not None and receipt-last_receipt>3):
            tracks={};phase_states={}
        previous_session=session
        if last_receipt is not None and 0<receipt-last_receipt<=3:coverage+=receipt-last_receipt
        last_receipt=receipt
        change=e.get('phaseChange')
        if change is not None:
            if change.get('absolute'):phase_states={};absolute_count+=1
            for p in change.get('phases',[]):
                n=str(p.get('phaseNumber'));code=p.get('status',0);old=phase_states.get(n);phase_states[n]=code
                if code in (1,2,3):valid.add(n)
                else:invalid.add(n)
                pt=stamp(p.get('timestamp') or e.get('timestamp'))
                if code==1 and old in (2,3) and pt:greens[n].append((session,pt))
            vectors.append(dict(phase_states))
        if 'frame' not in e or t is None:continue
        frame_count+=1
        for o in e['frame'].get('objects',[]):
            if str(o.get('classType')) not in VEHICLES or not o.get('id'):continue
            try:x=float(o['centerX']);y=float(o['centerY'])
            except (ValueError,TypeError,KeyError):continue
            if not math.isfinite(x+y) or math.hypot(x,y)>200:continue
            key=(session,o['id']);old=tracks.get(key)
            item={'t':t,'x':x,'y':y,'stopped_since':None,'stopped_point':None,'released':old.get('released',False) if old else False}
            if old:
                try:dt=(t-old['t']).total_seconds()
                except TypeError:dt=0
                if 0<dt<=3:
                    speed=math.hypot(x-old['x'],y-old['y'])/dt
                    if speed<=.5:
                        item['stopped_since']=old['stopped_since'] or old['t'];item['stopped_point']=(x,y)
                    elif speed<2:
                        item['stopped_since']=old['stopped_since'];item['stopped_point']=old['stopped_point']
                    elif speed<=25 and old['stopped_since'] and (old['t']-old['stopped_since']).total_seconds()>=2 and not item['released']:
                        heading=math.degrees(math.atan2(y-old['y'],x-old['x']))%360
                        releases.append({'session':session,'time':t,'x':old['stopped_point'][0],'y':old['stopped_point'][1],'heading':heading})
                        item['released']=True
            tracks[key]=item
    ordered=sorted(valid,key=int);groups=[];remaining=set(ordered)
    for n in ordered:
        if n not in remaining:continue
        group=[n]
        for m in ordered:
            if m==n or m not in remaining:continue
            shared=[(v[n],v[m]) for v in vectors if n in v and m in v and v[n] in (1,2,3) and v[m] in (1,2,3)]
            if len(shared)>=10 and len({a for a,b in shared})>=2 and all(a==b for a,b in shared):group.append(m)
        remaining.difference_update(group)
        if len(group)>1:groups.append(group)
    areas=defaultdict(list)
    for r in releases:
        key=(round(r['x']/15),round(r['y']/15),round(r['heading']/45)%8);areas[key].append(r)
    candidates=[]
    for items in areas.values():
        if len(items)<5:continue
        matching={}
        for n,changes in greens.items():
            matches=0
            for r in items:
                for session,t in changes:
                    if session!=r['session']:continue
                    try:delta=(r['time']-t).total_seconds()
                    except TypeError:continue
                    if 0<=delta<=10:matches+=1;break
            if matches:matching[n]=matches
        candidates.append({'local_x_m':round(sum(r['x'] for r in items)/len(items),2),'local_y_m':round(sum(r['y'] for r in items)/len(items),2),'release_events':len(items),'green_onset_matches_within_10s':matching,'interpretation':'Observed stop/release cluster, not a stop line or physical signal location'})
    return {'site':site,'start_receipt':start,'end_receipt':end,'frames':frame_count,'receipt_coverage':round(coverage/3600,3),'absolute_reports':absolute_count,'valid_phase_ids':ordered,'invalid_only_ids':sorted(invalid-valid,key=int),'identical_observed_state_groups':groups,'stop_release_events':len(releases),'candidate_areas':candidates,'physical_head_count':None,'verified_phase_mapping':False}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--database',default='data/ouster.sqlite3');p.add_argument('--output',default='data/signal-mapping-audit.json');args=p.parse_args()
    sites=json.loads(Path('config/sites.json').read_text())['sites'];db=sqlite3.connect(f'file:{args.database}?mode=ro',uri=True)
    results=[audit(db,s['id']) for s in sites if s['region']=='Toronto']
    Path(args.output).write_text(json.dumps({'method':'Exploratory single-hour audit; no physical-head inference or automatic map placement','sites':results},indent=2))
    for r in results:print(r['site'],{k:r.get(k) for k in ['frames','valid_phase_ids','identical_observed_state_groups','stop_release_events']})
