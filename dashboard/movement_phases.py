"""Receipt-timed phase evidence for each geometrically observed movement.
No phase ID/label join, physical-head assignment or controller verification.
"""
import bisect,json
from collections import Counter
from .movements import MOVEMENTS

def summarize(tracks,rows):
    samples=[];previous={};onsets={};cycles={};duration={};green_duration={};last_time=None;last_session=None
    for receipt,session,payload in rows:
        state=json.loads(payload)
        if not state.get('initialized'):continue
        if session!=last_session or (last_time is not None and receipt-last_time>10):previous={};onsets={}
        phases={str(n):p['status'] for n,p in state.get('phases',{}).items() if isinstance(p.get('received_at'),(int,float)) and 0<=receipt-p['received_at']<=180}
        for n,status in phases.items():
            if status=='GREEN' and previous.get(n) in ('RED','YELLOW'):
                onsets[n]=receipt;cycles[n]=cycles.get(n,0)+1
        if last_time is not None and session==last_session and receipt-last_time<=10:
            for n,status in previous.items():
                duration[n]=duration.get(n,0)+receipt-last_time
                if status=='GREEN':green_duration[n]=green_duration.get(n,0)+receipt-last_time
        samples.append((receipt,session,phases,dict(onsets)));previous=phases;last_time=receipt;last_session=session
    times=[s[0] for s in samples];evidence={code:[] for code in MOVEMENTS};counts=Counter();roles=Counter();unknown=0
    for track in tracks:
        movement=track['movement'];code=movement.get('movement')
        if code not in MOVEMENTS:unknown+=1;continue
        counts[code]+=1;roles[movement['role']]+=1
        # The first queue creep is not evidence that the movement is permitted.
        # Use the final stopped release shortly before entering the central area.
        points=track['points'];entry=next((p[0] for p in points if (p[1]**2+p[2]**2)**.5<=25),None)
        if entry is None:continue
        stopped=None;releases=[]
        for a,b in zip(points,points[1:]):
            if b[0]>entry:break
            dt=b[0]-a[0]
            if not 0<dt<=3:stopped=None;continue
            speed=((b[1]-a[1])**2+(b[2]-a[2])**2)**.5/dt
            if speed<=.5:stopped=a[0] if stopped is None else stopped
            elif speed>=2:
                if stopped is not None and a[0]-stopped>=2 and 8<=(a[1]**2+a[2]**2)**.5<=70 and 0<=entry-b[0]<=20:
                    idx=bisect.bisect_right(times,b[0])-1
                    if idx>=0:
                        t,session,phases,onset=samples[idx]
                        if 0<=b[0]-t<=6 and session==track['key'][0]:
                            releases.append({'time':b[0],'phases':phases,'onsets':onset})
                stopped=None
        if releases:evidence[code].append(releases[-1])
    output=[]
    for code,definition in MOVEMENTS.items():
        events=evidence[code];candidates=[]
        for n in sorted(duration):
            valid=[e for e in events if n in e['phases']]
            if not valid:continue
            green=sum(e['phases'][n]=='GREEN' for e in valid)/len(valid);red=sum(e['phases'][n]=='RED' for e in valid)/len(valid)
            near=[e for e in valid if n in e['onsets'] and 0<=e['time']-e['onsets'][n]<=12]
            onset=len(near)/len(valid);distinct=len({e['onsets'][n] for e in near});duty=green_duration.get(n,0)/max(duration[n],1)
            candidates.append(dict(phase_number=n,score=.6*green+.4*onset,releases=len(valid),green_fraction=green,red_fraction=red,onset_fraction=onset,release_cycles=distinct,green_duty=duty,observed_seconds=duration[n]))
        candidates.sort(key=lambda p:p['score'],reverse=True);best=candidates[0] if candidates else None
        margin=best['score']-candidates[1]['score'] if len(candidates)>1 else 1
        accepted=bool(best and best['observed_seconds']>=600 and best['releases']>=8 and best['release_cycles']>=3 and best['green_fraction']>=.8 and best['red_fraction']<=.1 and best['onset_fraction']>=.5 and best['green_fraction']>=1.5*best['green_duty'] and margin>=.2)
        output.append(dict(movement=code,**definition,observed_tracks=counts[code],phase_numbers=[best['phase_number']] if accepted else [],phase_mapping='estimated' if accepted else 'insufficient_or_ambiguous',qualifying_releases=len(events),candidates=candidates[:4]))
    return dict(movements=output,unknown_tracks=unknown,roles=dict(roles),phase_samples=len(samples),phase_recording_start=times[0] if times else None,phase_recording_end=times[-1] if times else None,
        note='Movement is inferred from complete 2D paths; phase mapping from repeated stop/release evidence. Provisional alignment, receipt timing and permissive turns limit inference. Correlated phases remain ambiguous; no verified label/ID join.')
