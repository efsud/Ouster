"""Bounded unattended experiment, not an autonomous code-writing agent.

Uses existing collectors; never restarts authentication or edits sensor settings.
Retains metrics/models, not eight hours of raw trajectory data. Stops at deadline.
"""
import argparse,hashlib,json,time
from pathlib import Path
import numpy as np
from .archive_extension import cases
from .endpoint_speed import reconstruct
from .reconstruction_study import metrics,summarize
ROOT=Path(__file__).resolve().parents[1]
POLICY={'negative_speed_limit_mps':.1,'position_span_limit_m':.1,'trend_limit_mps':.05,'step_speed_limit_mps':.5}

def atomic(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix('.tmp');temp.write_text(json.dumps(value,indent=2,allow_nan=False));temp.replace(path)

def identity(site, track):
    key=track.get('source_key',[])
    return json.dumps([site['id'],key[:2]]) if len(key)>=2 else None

def earlier_ids(snapshot, end):
    return sorted({identity(s,t) for s in snapshot['sites'] for t in s['tracks']
                   if t['points'][0][0]<end and identity(s,t) is not None})

def calibrate(snapshot):
    values=[];acc=[]
    for site in snapshot['sites']:
        for tr in site['tracks']:
            p=np.asarray(tr['points'],float)
            if tr['class_type']!='2' or p[-1,0]>.5*(snapshot['end']-snapshot['start']):continue
            values.extend(p[:,2][p[:,2]>=0]);dt=np.diff(p[:,0]);valid=(dt>0)&(dt<=1.5);acc.extend((np.diff(p[:,2])[valid]/dt[valid]).tolist())
    if len(values)<100 or len(acc)<100:raise ValueError('Insufficient training samples')
    return dict(vmax=float(np.clip(np.quantile(values,.995),5,35)),amin=float(np.clip(np.quantile(acc,.01),-6,-1)),amax=float(np.clip(np.quantile(acc,.99),1,4)))

def subset(snapshot,lo,hi,excluded=()):
    excluded=set(excluded)
    return dict(snapshot,sites=[dict(s,tracks=[t for t in s['tracks'] if t['points'][0][0]>=lo and t['points'][-1][0]<=hi and identity(s,t) is not None and identity(s,t) not in excluded]) for s in snapshot['sites']])

def sample(snapshot,lo,hi,limit=2,excluded=()):
    return cases(subset(snapshot,lo,hi,excluded),'test',limit)

def evaluate(rows,params,deadline):
    scores={'strict':{},'noise':{}};details=[]
    for i,row in enumerate(rows):
        if time.time()>=deadline:break
        rank,site,tr,gap,(a,b,truth)=row
        baseline=reconstruct(a,b,params,None);new=baseline if baseline['state']=='candidate' else reconstruct(a,b,params,POLICY)
        entry=dict(site=site['id'],name=site['name'],gap_s=gap,rank=rank,states={},metrics={})
        for name,r in [('strict',baseline),('noise',new)]:
            entry['states'][name]=r['state']
            if r['state']=='candidate':scores[name][i]=metrics(r['points'],truth,params);entry['metrics'][name]=scores[name][i]
        details.append(entry)
    summary={}
    for method,sc in scores.items():
        new=set(sc)-set(scores['strict']);common=set(sc)&set(scores['strict'])
        summary[method]=dict(eligible=len(rows),evaluated=len(details),accepted=len(sc),all=summarize(list(sc.values())),common=summarize([sc[i] for i in common]),new=summarize([sc[i] for i in new]),
            sites={s:{'eligible':sum(d['site']==s for d in details),'accepted':sum(d['site']==s and method in d['metrics'] for d in details),
                'new':summarize([sc[i] for i in new if details[i]['site']==s])} for s in sorted({d['site'] for d in details})})
    return dict(summary=summary,cases=details)

def finishable_new(metrics_):
    return metrics_.get('n',0)>=10 and metrics_['mae_m']<=3 and metrics_['speed_mae_mps']<=1 and metrics_['p95_case_mae_m']<=10

def aggregate(output, complete=False):
    """Summarize disjoint test windows; never select a method from test scores."""
    output=Path(output);summary={'state':'complete' if complete else 'running','updated_at':time.time(),'regions':{},
        'limitations':['Repeated gap lengths are correlated cases, not independent vehicles.',
        'Actual cross-sensor identities and clock offsets remain unverified.',
        'Candidate corrections may be withheld at individual sites.',
        'No simulated continuations; unresolved observations stay missing.']}
    for region in ('florida','finch'):
        reports=[json.loads(p.read_text()) for p in sorted((output/region).glob('cycle-*.json'))]
        methods={}
        for method in ('strict','noise'):
            rows=[c['metrics'][method] for r in reports for c in r['results']['cases'] if method in c['metrics']]
            new=[c['metrics'][method] for r in reports for c in r['results']['cases'] if method in c['metrics'] and 'strict' not in c['metrics']]
            methods[method]={'eligible':sum(r['results']['summary'][method]['evaluated'] for r in reports),'accepted':len(rows),'all':summarize(rows),'new':summarize(new)}
        associations=[r['association'] for r in reports if 'association' in r]
        extra=output/region/'global-comparison-001.json'
        if extra.exists() and reports and 'association' not in reports[0]:associations.insert(0,json.loads(extra.read_text()))
        summary['regions'][region]={'windows':len(reports),'geometry_versions':sorted({r.get('geometry_version','inter-sensor-chord-v1') for r in reports}),'methods':methods,
            'association':{method:{k:sum(r['totals'].get(method,{}).get(k,0) for r in associations) for k in ('eligible','matched','correct','false')} for method in ('baseline','physics_screened','global_partial')}}
        shape=[r['shape_association'] for r in reports if 'shape_association' in r]
        summary['regions'][region]['shape_prospective']={'windows':len(shape),'time_bases':sorted({r.get('time_basis','receipt') for r in shape}),
            'totals':{method:{k:sum(r['totals'].get(method,{}).get(k,0) for r in shape) for k in ('eligible','matched','correct','false')} for method in ('current','0','0.5')}}
        lateral=[r['lateral_motion_prospective'] for r in reports if 'lateral_motion_prospective' in r]
        lateral_cases=[c for r in lateral for c in r['cases']];accepted=[c for c in lateral_cases if c['accepted']]
        summary['regions'][region]['lateral_prospective']={'windows':len(lateral),'eligible':len(lateral_cases),'accepted':len(accepted),
            'distinct_accepted_ids':len({c['identity_hash'] for c in accepted}),'quality':summarize([c['metrics'] for c in accepted]),
            'lateral_mae_m':float(np.mean([c['lateral_mae_m'] for c in accepted])) if accepted else None}
        site_rows=[c for r in reports for c in r.get('site_policy_prospective',{}).get('cases',[])]
        new=[c['metrics']['noise'] for c in site_rows if 'noise' in c['metrics'] and 'strict' not in c['metrics']]
        summary['regions'][region]['site_policy_prospective']={'evaluated':len(site_rows),'new':summarize(new)}
    atomic(output/'summary.json',summary)
    return summary

def run(output,deadline,interval=1800):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    import fcntl
    lock=open(output/'campaign.lock','w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    status=dict(state='running',started_at=time.time(),deadline=deadline,kind='bounded existing-code evaluation, not continuous agent reasoning',regions={},errors=[])
    if (output/'status.json').exists():
        previous_status=json.loads((output/'status.json').read_text())
        status.update(started_at=previous_status.get('started_at',status['started_at']),regions=previous_status.get('regions',{}),errors=previous_status.get('errors',[]))
    models={};last={};last_lateral={};lateral_ids={'florida':set(),'finch':set()};cycle=0
    for region in ('florida','finch'):
        folder=output/region
        if (folder/'model.json').exists():models[region]=json.loads((folder/'model.json').read_text())
        for path in sorted(folder.glob('cycle-*.json')):
            previous=json.loads(path.read_text());last[region]=previous['window'][1];cycle=max(cycle,previous['cycle'])
            if 'lateral_motion_prospective' in previous:
                experiment=previous['lateral_motion_prospective'];last_lateral[region]=experiment['window'][1]
                lateral_ids[region].update(r['identity_hash'] for r in experiment['cases'])
            status['regions'][region]={'state':'evaluated','last_report':f'{region}/{path.name}','summary':previous['results']['summary'],'snapshot_end':previous['window'][1]}
    atomic(output/'status.json',status)
    while time.time()<deadline:
        cycle+=1
        for region in ('florida','finch'):
            if time.time()>=deadline:break
            try:
                path=ROOT/f'data/{region}-rolling/snapshot.json';raw=path.read_bytes();s=json.loads(raw)
                state=status['regions'].setdefault(region,{})
                state.update(snapshot_end=s['end'],age_s=max(0,time.time()-s['end']),missing_sites=[x['id'] for x in s['sites'] if not x['frames']])
                if time.time()-s['end']>3600:state['state']='waiting_for_fresh_recording';continue
                if last.get(region)==s['end']:continue
                folder=output/region;folder.mkdir(exist_ok=True)
                if region not in models:
                    if region=='florida':
                        model=json.loads((ROOT/'data/reconstruction/word-v1-collection/evaluation-001/report.json').read_text())
                        params=model['calibration']['parameters'];policy=json.loads((ROOT/'config/reconstruction/florida-endpoint-speed.json').read_text())
                        models[region]={'parameters':params,'endpoint_policy':POLICY,'excluded_sites':policy.get('excluded_sites',[]),'frozen_at':time.time()}
                    else:
                        params=calibrate(s);duration=s['end']-s['start']
                        validation=evaluate(sample(s,.5*duration+30,.75*duration-30,excluded=earlier_ids(s,.5*duration)),params,deadline)
                        atomic(folder/'validation.json',validation)
                        excluded=[site for site,r in validation['summary']['noise']['sites'].items() if not finishable_new(r['new'])]
                        models[region]={'parameters':params,'endpoint_policy':POLICY if finishable_new(validation['summary']['noise']['new']) else None,'excluded_sites':excluded,'frozen_at':time.time()}
                    models[region]['excluded_test_ids']=earlier_ids(s,.75*(s['end']-s['start']))
                    models[region]['first_test_start']=s['start']+.75*(s['end']-s['start'])+30
                    atomic(folder/'model.json',models[region])
                model=models[region];begin=max(model['first_test_start'],last.get(region,s['start'])+30)
                validation=evaluate(sample(s,max(0,begin-s['start']),s['end']-s['start']-30,excluded=model.get('excluded_test_ids',[])),model['parameters'],deadline)
                report=dict(cycle=cycle,region=region,snapshot_sha256=hashlib.sha256(raw).hexdigest(),window=[s['start'],s['end']],evaluated_window=[begin,s['end']-30],
                    model=model,geometry_version=s.get('geometry_version','inter-sensor-chord-v1'),endpoint_context_version=s.get('endpoint_context_version','legacy-five-points'),ingestion_epochs=s.get('ingestion_epochs',[]),results=validation,limitations=['No ground truth between sensors.','Known training/validation IDs excluded from test; multiple gap lengths per test vehicle are not independent.','Geometry version is recorded; projection changes are not evidence of improved prediction accuracy.','No parameter retuning on later test windows.','No automatic promotion from these test scores.'])
                from .campaign_association import evaluate as association_evaluate
                report['association']=association_evaluate(subset(s,max(0,begin-s['start']),s['end']-s['start']-30,model.get('excluded_test_ids',[])),model['parameters'],deadline)
                site_protocol=ROOT/'data/reconstruction/site-policy-review/protocol.json'
                if region=='finch' and site_protocol.exists():
                    proposal=json.loads(site_protocol.read_text())
                    unseen=subset(s,max(0,max(begin,proposal['after'])-s['start']),s['end']-s['start']-30,proposal['excluded_ids'])
                    unseen['sites']=[site for site in unseen['sites'] if site['id'] in proposal['sites']]
                    # Site-selection protocol uses the frozen numerical policy;
                    # never substitute a later edited threshold silently.
                    if proposal['parameters']!=POLICY:raise ValueError('Prospective endpoint policy differs from frozen implementation')
                    report['site_policy_prospective']=evaluate(cases(unseen,'test',4),model['parameters'],deadline)
                    report['site_policy_prospective']['protocol_sha256']=hashlib.sha256(site_protocol.read_bytes()).hexdigest()
                shape_protocol=ROOT/'data/reconstruction/shape-review/protocol.json'
                if shape_protocol.exists() and any(t.get('dimensions') for site in s['sites'] for t in site['tracks']):
                    protocol=json.loads(shape_protocol.read_text());plan=protocol['regions'][region]
                    from .validate_shape_association import score as shape_score
                    shape_begin=max(begin,plan['after'])
                    shape_input=subset(s,max(0,shape_begin-s['start']),s['end']-s['start']-30,plan['excluded_ids'])
                    shape_report={'selected_method':'kinematic_0.01','calibration':{'parameters':model['parameters']}}
                    report['shape_association']=shape_score(shape_input,shape_report,['current',0,protocol['weight']],deadline=deadline)
                    report['shape_association']['time_basis']=s.get('time_basis','receipt')
                    report['shape_association']['protocol_sha256']=hashlib.sha256(shape_protocol.read_bytes()).hexdigest()
                    report['shape_association']['note']='Frozen 0.5 shape weight; no tuning. Single-sensor spatial masks only.'
                lateral_protocol=ROOT/'data/reconstruction/lateral-gap-review/protocol.json'
                if lateral_protocol.exists() and time.time()<deadline:
                    proposal=json.loads(lateral_protocol.read_text())
                    from .validate_lateral_gaps import run as lateral_evaluate
                    lateral_report={'selected_method':'kinematic_0.01','calibration':{'parameters':model['parameters']}}
                    lateral_begin=max(proposal['after'],last_lateral.get(region,0)+30)
                    report['lateral_motion_prospective']=lateral_evaluate(region,lateral_report,after=lateral_begin,
                        excluded_ids=set(proposal['excluded_ids'][region])|lateral_ids[region],max_gap=proposal['max_gap_s'],deadline=deadline)
                    report['lateral_motion_prospective']['protocol_sha256']=hashlib.sha256(lateral_protocol.read_bytes()).hexdigest()
                    last_lateral[region]=report['lateral_motion_prospective']['window'][1]
                    lateral_ids[region].update(r['identity_hash'] for r in report['lateral_motion_prospective']['cases'])
                atomic(folder/f'cycle-{cycle:03}.json',report);last[region]=s['end'];state.update(state='evaluated',last_report=f'{region}/cycle-{cycle:03}.json',summary=validation['summary'])
                # Publish only a calibration/validation-selected Finch model for a
                # separate layer worker; test scores cannot change its parameters.
                if region=='finch':
                    initial={'state':'evaluated_ablation','selected_method':'kinematic_0.01','calibration':{'parameters':model['parameters']},'test':{k:{'common':v['common'],'accepted':v['accepted'],'eligible':v['eligible']} for k,v in validation['summary'].items()},'uncertainty':{'state':'not_calibrated'},'source':'Finch first-half calibration; no Florida parameter transfer'}
                    atomic(ROOT/'data/reconstruction/finch/report.json',initial)
                    atomic(ROOT/'data/reconstruction/finch/policy.json',model)
                    atomic(ROOT/'data/reconstruction/finch/status.json',{'state':'evaluated_ablation','updated_at':time.time(),'report':str(ROOT/'data/reconstruction/finch/report.json'),'validation_label':'provisional masked local evaluation; cross-sensor identities unverified'})
                status['updated_at']=time.time();atomic(output/'status.json',status)
            except Exception as exc:
                status['errors'].append({'region':region,'time':time.time(),'type':type(exc).__name__});status['errors']=status['errors'][-30:]
                status['regions'].setdefault(region,{})['state']='evaluation_error';atomic(output/'status.json',status)
                print(region,type(exc).__name__,str(exc)[:120],flush=True)
        status['updated_at']=time.time();status['cumulative']=aggregate(output)['regions'];atomic(output/'status.json',status)
        next_run=min(deadline,time.time()+interval)
        while time.time()<next_run:time.sleep(min(30,max(0,next_run-time.time())))
    status.update(state='complete',finished_at=time.time(),cumulative=aggregate(output,complete=True)['regions']);atomic(output/'status.json',status);lock.close()
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--deadline',type=float,required=True);p.add_argument('--interval',type=float,default=1800);a=p.parse_args();run(a.output,a.deadline,a.interval)
