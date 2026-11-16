"""Exploratory receipt-timed stop/release correlation, never controller verification."""
import json
import math
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / 'data/signal-estimates.json'
VEHICLES = {'1','2','3','4','5','6','7','8','9','15'}
AXES = {'E': (1,0), 'W': (-1,0), 'N': (0,1), 'S': (0,-1)}


def point(obj, site):
    x, y = float(obj.get('centerX',0)), float(obj.get('centerY',0))
    if site.get('preview_mirror_y'): y = -y
    a = math.radians(site.get('preview_rotation_deg',220))
    p = (x*math.cos(a)-y*math.sin(a), x*math.sin(a)+y*math.cos(a))
    if not all(math.isfinite(v) for v in p) or math.hypot(*p)>200: raise ValueError('outside scene')
    return p


def classify(vector):
    length = math.hypot(*vector)
    if not length: return None
    d = max(AXES, key=lambda d: sum(a*b for a,b in zip(vector,AXES[d])))
    return d if sum(a*b for a,b in zip(vector,AXES[d]))/length >= math.cos(math.radians(35)) else None


class Learner:
    def __init__(self, site):
        self.site=site; self.session=None; self.last=None; self.reset()

    def reset(self):
        self.tracks={}; self.previous={}; self.onsets={}; self.cycles=[]
        self.samples=[]; self.releases=[]; self.last_key=None; self.started=None

    def ingest(self, receipt, session, key, objects, phase_state):
        if key==self.last_key: return
        if self.last is not None and receipt<=self.last: return
        if session!=self.session or (self.last is not None and receipt-self.last>5): self.reset()
        self.session=session; self.last=receipt; self.last_key=key
        if not phase_state.get('initialized') or phase_state.get('session')!=session:
            self.tracks={}; return
        self.started=self.started or receipt
        phases={n:p['status'] for n,p in phase_state.get('phases',{}).items()
                if 0<=receipt-p['received_at']<=180 and p['status'] in ('GREEN','YELLOW','RED')}
        for n,s in phases.items():
            if s=='GREEN' and self.previous.get(n) in ('RED','YELLOW'):
                self.onsets[n]=receipt; self.cycles.append((receipt,n))
        self.previous=phases
        self.samples.append((receipt,phases))
        self.samples=[x for x in self.samples if x[0]>=receipt-3600]
        self.cycles=[x for x in self.cycles if x[0]>=receipt-3600]
        self.releases=[x for x in self.releases if x['time']>=receipt-3600]
        self.tracks={k:v for k,v in self.tracks.items() if receipt-v['time']<=3}
        for obj in objects:
            if str(obj.get('classType')) not in VEHICLES or not obj.get('id'): continue
            try: p=point(obj,self.site)
            except (ValueError,TypeError): continue
            old=self.tracks.get(obj['id']); item={'point':p,'time':receipt,'stopped':None,'pending':None}
            if old:
                dt=receipt-old['time']; v=(p[0]-old['point'][0],p[1]-old['point'][1])
                speed=math.hypot(*v)/dt
                item['pending']=old['pending']
                if speed<=.5: item['stopped']=old['stopped'] or old['time']
                elif speed<2: item['stopped']=old['stopped']
                elif speed<=25 and old['stopped'] is not None and old['time']-old['stopped']>=2 and not old['pending']:
                    direction=classify(v)
                    if direction:
                        length=math.hypot(*v); unit=(v[0]/length,v[1]/length)
                        along=sum(a*b for a,b in zip(old['point'],unit))
                        lateral=abs(old['point'][0]*unit[1]-old['point'][1]*unit[0])
                        if -80<=along<=-8 and lateral<=20:
                            item['pending']={'time':receipt,'direction':direction,'unit':unit,'origin':old['point'],
                                'phases':dict(phases),'onset_times':dict(self.onsets),'near_onset':[n for n,t in self.onsets.items() if 0<=receipt-t<=12]}
                pending=item['pending']
                if pending:
                    u=pending['unit']; delta=(p[0]-pending['origin'][0],p[1]-pending['origin'][1])
                    lateral=abs(delta[0]*u[1]-delta[1]*u[0])
                    aligned=speed<2 or (math.hypot(*v)>0 and sum(a*b for a,b in zip(v,u))/math.hypot(*v)>=math.cos(math.radians(25)))
                    if receipt-pending['time']>60 or lateral>12 or not aligned: item['pending']=None
                    elif sum(a*b for a,b in zip(p,u))>=8:
                        self.releases.append(pending); item['pending']=None
            self.tracks[obj['id']]=item

    def report(self, now):
        out={}
        for direction in AXES:
            events=[e for e in self.releases if e['direction']==direction]
            candidates=[]
            for n in sorted({n for _,s in self.samples for n in s}):
                observed=[s[n] for _,s in self.samples if n in s]
                matched=[e for e in events if n in e['phases']]
                if not matched: continue
                green=sum(e['phases'][n]=='GREEN' for e in matched)/len(matched)
                red=sum(e['phases'][n]=='RED' for e in matched)/len(matched)
                onset=sum(n in e['near_onset'] for e in matched)/len(matched)
                duty=observed.count('GREEN')/len(observed)
                cycles=sum(k==n for _,k in self.cycles)
                release_cycles=len({e.get('onset_times',{}).get(n) for e in matched if n in e['near_onset'] and n in e.get('onset_times',{})})
                score=.6*green+.4*onset
                candidates.append(dict(phase=n,score=round(score,3),green_fraction=round(green,3),red_fraction=round(red,3),
                    onset_fraction=round(onset,3),green_duty=round(duty,3),cycles=cycles,release_cycles=release_cycles,releases=len(matched)))
            candidates.sort(key=lambda x:x['score'],reverse=True)
            best=candidates[0] if candidates else None
            span=self.samples[-1][0]-self.samples[0][0] if len(self.samples)>1 else 0
            margin=best['score']-candidates[1]['score'] if len(candidates)>1 else 1
            accepted=bool(best and span>=600 and best['releases']>=8 and best['cycles']>=3 and best['release_cycles']>=3 and
                best['green_fraction']>=.8 and best['red_fraction']<=.1 and best['onset_fraction']>=.5 and
                best['green_fraction']>=1.5*best['green_duty'] and margin>=.2)
            reason='Estimated from repeated straight-through stop/release timing' if accepted else 'Insufficient or ambiguous movement/phase evidence'
            out[direction]=dict(accepted=accepted,phase_numbers=[best['phase']] if accepted else [],
                confidence='provisional' if accepted else 'insufficient',reason=reason,
                matched_releases=len(events),margin=round(margin,3) if best else None,candidates=candidates[:5])
        return dict(site=self.site['id'],session=self.session,last_receipt=self.last,updated_at=now,
                    sample_count=len(self.samples),directions=out,
                    note='Estimated, not controller-verified. Receipt timing and provisional geometry; correlation is not proof. No physical-head mapping.')


def main():
    import sqlite3
    from .server import sites
    learners={s['id']:Learner(s) for s in sites() if s['region'] in ('Toronto','Florida')}
    databases={region:sqlite3.connect(f'file:{ROOT / "data" / name}?mode=ro',uri=True)
               for region,name in [('Toronto','finch-live.sqlite3'),('Florida','florida-live.sqlite3')]}
    for db in databases.values(): db.row_factory=sqlite3.Row
    last_save=0
    while True:
        now=time.time()
        for learner in learners.values():
            db=databases[learner.site['region']]
            # One read transaction pairs the preview with the accumulated phase state.
            try:
                db.execute('BEGIN')
                row=db.execute('SELECT * FROM preview_frames WHERE site=?',(learner.site['id'],)).fetchone()
                signal=db.execute('SELECT payload FROM live_signal_state WHERE site=?',(learner.site['id'],)).fetchone()
                db.rollback()
                if row and signal and 0<=now-row['received_at']<=3:
                    learner.ingest(row['received_at'],row['session'],row['event_key'],json.loads(row['payload']).get('frame',{}).get('objects',[]),json.loads(signal[0]))
            except sqlite3.Error:
                db.rollback()
        if now-last_save>=5:
            value={'version':1,'updated_at':now,'sites':{k:l.report(now) for k,l in learners.items()}}
            temp=REPORT.with_suffix('.tmp'); temp.write_text(json.dumps(value)); temp.replace(REPORT); last_save=now
        time.sleep(.5)

if __name__=='__main__': main()
