"""Frozen-parameter local/outage/spatial-mask ablation of integrated priors."""
import argparse,bisect,hashlib,json,sqlite3,time
from pathlib import Path
from collections import Counter
import numpy as np
from .reconstruction_study import masked_case,metrics,summarize,partition_track
from .validate_spatial import masked
from .integrated_reconstruction import reconstruct
from .reconstruction_layers import prediction
from dashboard.movement_phases import summarize as phase_summary


def phase_inputs(snapshot,db):
    if snapshot.get('time_basis','receipt')!='receipt':
        # Phase delivery timestamps have not undergone the object-frame timing
        # correction. Never infer signal permission by joining unlike clocks.
        return {site['id']:({},[]) for site in snapshot['sites']}
    cutoff=snapshot['start']+.6*(snapshot['end']-snapshot['start']);output={}
    for site in snapshot['sites']:
        rows=db.execute('SELECT received,session,payload FROM phase_samples WHERE site=? AND received>=? AND received<=? ORDER BY received',(site['id'],snapshot['start'],snapshot['end'])).fetchall()
        tracks=[]
        for tr in site['tracks']:
            if tr['receipt_end']>=cutoff or tr.get('movement',{}).get('movement') not in ('WE','EW'):continue
            p=tr['points'];times=np.array([x[0] for x in p]);y=np.interp(times,[times[0],times[-1]],[tr.get('lateral_start_m',0),tr.get('lateral_end_m',0)])
            tracks.append(dict(key=tr['source_key'],movement=tr['movement'],points=[[t+snapshot['start'],x-site['station_m'],float(lat)] for (t,x,v),lat in zip(p,y)]))
        calibration=phase_summary(tracks,[row for row in rows if row[0]<cutoff])
        mapping={m['movement']:m['phase_numbers'][0] for m in calibration['movements'] if m['phase_numbers']}
        output[site['id']]=(mapping,rows)
    return output


def signal_for(site,tr,a,b,inputs,start):
    mapping,rows=inputs[site['id']];phase=mapping.get('WE' if tr['direction']=='eastbound' else 'EW')
    if not phase:return None
    timestamps=[r[0] for r in rows];series=[]
    for t in np.linspace(a['t'],b['t'],max(2,int((b['t']-a['t'])*2)+1)):
        absolute=start+t;i=bisect.bisect_right(timestamps,absolute)-1
        if i<0:return None
        receipt,session,payload=rows[i];state=json.loads(payload);p=state.get('phases',{}).get(phase)
        if session!=tr['source_key'][0] or absolute-receipt>6 or not p or not state.get('initialized'):return None
        if not 0<=absolute-p.get('received_at',-1e20)<=180:return None
        factor={'GREEN':1.,'RED':0.,'YELLOW':.5}.get(p.get('status'))
        if factor is None:return None
        series.append([float(t),factor])
    return series


def hide_context(site,target,a,b,task,band=None):
    """Mask all objects for outages/spatial blind spots, not just target truth."""
    tracks=[]
    for tr in site['tracks']:
        if tr['source_key'][:2]==target['source_key'][:2]:continue
        points=tr['points']
        if task=='outage':points=[p for p in points if not a['t']<p[0]<b['t']]
        elif task=='spatial':points=[p for p in points if not band[0]<p[1]<band[1]]
        if len(points)>=2:tracks.append(dict(tr,points=points))
    return dict(site,tracks=tracks)


def run(source,study,buffer,output,limit=12):
    raw=Path(source).read_bytes();s=json.loads(raw);frozen=json.loads(Path(study).read_text());plan=frozen['plan'];params=frozen['calibration']['parameters']
    db=sqlite3.connect(f'file:{Path(buffer).resolve()}?mode=ro',uri=True);signals=phase_inputs(s,db);db.close()
    methods=['current','newell','ctm_no_signal','ctm','integrated'];groups={}
    for site in s['sites']:
        for tr in site['tracks']:
            split=partition_track(site['id'],tr,s,plan)
            if split not in ('validation','test'):continue
            key=json.dumps([site['id'],tr['source_key'],tr['points'][0][0]])
            rank=hashlib.sha256(key.encode()).hexdigest()
            gap=(5,10,20,30)[int(rank[:8],16)%4];case=masked_case(tr,gap)
            if case:
                for task in ('local','outage'):groups.setdefault((split,task,site['id'],tr['direction']),[]).append((rank,site,tr,case,None,gap))
            width=(20,50)[int(rank[8:16],16)%2];case=masked(tr,site['station_m'],width)
            if case:
                a,b,truth,*_=case;sign=1 if tr['direction']=='eastbound' else -1
                a=dict(a,x=a['x']*sign,v=a['v']*sign);b=dict(b,x=b['x']*sign,v=b['v']*sign);truth=truth.copy();truth[:,1]*=sign
                groups.setdefault((split,'spatial',site['id'],tr['direction']),[]).append((rank,site,tr,(a,b,truth),(site['station_m']-width/2,site['station_m']+width/2),width))
    result=dict(created_at=time.time(),source_sha256=hashlib.sha256(raw).hexdigest(),source_window=[s['start'],s['end']],
        parameters=params,phase_mapping={k:v[0] for k,v in signals.items()},methods=methods,results={},
        assumptions={'cell_length_m':20,'region_m':[-120,120],'stopline':'intersection reference at 0 m, provisional','backward_wave_mps':5,'jam_veh_per_m':.2,'newell_tau_s':1,'reference_blend':.5,'speed_envelope_halfwidth_mps':5},
        limitations=['Phase mapping fitted only on first 60% at each site; estimated, not controller verified','Signal mapping uses approximate lateral positions between visible endpoints','Parameters frozen; CTM/Newell nominal assumptions not field calibrated','Spatial masks give known matching endpoints; no cross-sensor identity validation','No ground truth between real intersections','Target ID excluded entirely from prior context; all-object masks for outages and blind bands','No learned prediction of unobserved side-street arrivals; restricted lane-group scenario','Correlated same-day masks; short/long and stop statistics must be considered separately'])
    for split in ('validation','test'):
        for task in ('local','outage','spatial'):
            cases=[]
            for (part,kind,site_id,direction),values in sorted(groups.items()):
                if part==split and kind==task:cases.extend(sorted(values,key=lambda row:row[0])[:limit])
            scores={m:{} for m in methods};support={m:Counter() for m in methods};availability={m:{} for m in methods};strata={}
            for cid,(_,site,tr,(a,b,truth),band,size) in enumerate(cases):
                context=hide_context(site,tr,a,b,task,band);signal=None if task=='outage' else signal_for(site,tr,a,b,signals,s['start'])
                strata[cid]=size
                for mode in methods:
                    if mode=='current':
                        p=prediction(a,b,frozen,exact_join=True)
                        if p is None:continue
                        p=np.array(p)
                    else:
                        r=reconstruct(context,tr,a,b,params,signal=None if mode=='ctm_no_signal' else signal,mode='ctm' if mode=='ctm_no_signal' else mode)
                        availability[mode][cid]={k:bool(r[k]) for k in ('leader_used','ctm_used','signal_used')}
                        support[mode]['leader_cases']+=r['leader_used'];support[mode]['ctm_cases']+=r['ctm_used'];support[mode]['signal_cases']+=r['signal_used'] and mode!='newell'
                        if r['state']!='candidate':continue
                        p=r['points']
                    scores[mode][cid]=metrics(p,truth,params)
            common=set.intersection(*(set(rows) for rows in scores.values())) if cases else set()
            result['results'][split+'_'+task]={m:dict(eligible=len(cases),accepted=len(rows),common=summarize([rows[i] for i in common]),
                by_gap_or_width={str(size):summarize([rows[i] for i in common if strata[i]==size]) for size in sorted(set(strata.values()))},
                moving=summarize([rows[i] for i in common if rows[i]['moving']]),support=dict(support[m]),
                common_support={k:sum(availability[m].get(i,{}).get(k,False) for i in common) for k in ('leader_used','ctm_used','signal_used')},
                common_all_priors=sum(all(availability[m].get(i,{}).get(k,False) for k in ('leader_used','ctm_used','signal_used')) for i in common)) for m,rows in scores.items()}
            if common:
                gain=np.array([scores['current'][i]['mae_m']-scores['integrated'][i]['mae_m'] for i in sorted(common)])
                rng=np.random.default_rng(117);means=np.mean(rng.choice(gain,size=(2000,len(gain)),replace=True),axis=1)
                result.setdefault('paired_gain',{})[split+'_'+task]={'mean_improvement_m':float(gain.mean()),'bootstrap95_m':np.quantile(means,[.025,.975]).tolist(),
                    'warning':'Exploratory mask-level interval; not independent days or sensor ground truth'}
    result['deployment']='Experimental comparison only; existing dashboard estimator unchanged'
    Path(output).write_text(json.dumps(result,indent=2,allow_nan=False));return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--snapshot',required=True);p.add_argument('--study',required=True);p.add_argument('--buffer',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    r=run(a.snapshot,a.study,a.buffer,a.output)
    print(json.dumps({'phase_mapping':r['phase_mapping'],'results':{k:{m:{'n':v['common']['n'],'mae':v['common'].get('mae_m'),'support':v['support']} for m,v in rows.items()} for k,rows in r['results'].items()}},indent=2))
