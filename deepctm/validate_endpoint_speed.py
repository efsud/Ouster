"""Freeze a stationary-noise correction on AM, test untouched PM second hour.

Never score the new test period before writing selection.json. Whole IDs seen
in the earlier PM hour are excluded from the new test. Every rejected case and
correction is retained; inferred curves never become training truth.
"""
import argparse,hashlib,json,time
from collections import Counter
from pathlib import Path
import numpy as np
from .archive_extension import cases,GAPS
from .endpoint_speed import reconstruct
from .reconstruction_study import metrics,summarize

CONFIGS={f'noise_{x}':dict(negative_speed_limit_mps=x,position_span_limit_m=x,trend_limit_mps=.05,step_speed_limit_mps=.5) for x in (.1,.25,.5)}

def identity(row):return (row[1]['id'],*row[2]['source_key'][:2])
def save(path,obj):
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(obj,indent=2,allow_nan=False));temp.replace(path)

def evaluate(rows,methods,params,path):
    scores={m:{} for m in methods};audit=[]
    for i,(rank,site,tr,gap,(a,b,truth)) in enumerate(rows):
        strict=reconstruct(a,b,params,None);case={'key':rank,'site':site['id'],'direction':tr['direction'],'gap_s':gap,'results':{}}
        for name,config in methods.items():
            result=strict if name=='strict' or strict['state']=='candidate' else reconstruct(a,b,params,config)
            case['results'][name]={k:result[k] for k in ('state','reason','endpoint_corrections','correction_rejection','solver') if k in result}
            if result['state']=='candidate':
                scores[name][i]=metrics(result['points'],truth,params);case['results'][name]['metrics']=scores[name][i]
        audit.append(case)
        if i%20==0:print(path.stem,i,len(rows),flush=True)
    save(path,audit);base=set(scores['strict']);summary={}
    for name,sc in scores.items():
        common=base&set(sc);new=set(sc)-base
        summary[name]={'eligible':len(rows),'accepted':len(sc),'coverage':len(sc)/len(rows) if rows else 0,
            'all_accepted':summarize(list(sc.values())),'common_with_strict':summarize([sc[i] for i in sorted(common)]),
            'newly_accepted':summarize([sc[i] for i in sorted(new)]),'lost_strict_cases':len(base-set(sc)),
            'by_gap':{str(g):{'eligible':sum(r[3]==g for r in rows),'accepted':sum(rows[i][3]==g for i in sc),
                'all_accepted':summarize([sc[i] for i in sc if rows[i][3]==g]),'newly_accepted':summarize([sc[i] for i in new if rows[i][3]==g])} for g in GAPS}}
    return summary,audit

def run(am,previous_pm,test,study,output):
    folder=Path(output);folder.mkdir(parents=True,exist_ok=True)
    if (folder/'selection.json').exists():raise FileExistsError('Use a new output folder; preserve frozen selection and results')
    morning=json.loads(Path(am).read_text());params=json.loads(Path(study).read_text())['calibration']['parameters']
    train=cases(morning,'train',10000);train_ids={identity(r) for r in train};validation=[r for r in cases(morning,'validation',5) if identity(r) not in train_ids]
    # Diagnostic uses only visible endpoint context in the AM training portion.
    speeds=[ep['v'] for *_,(a,b,truth) in train for ep in (a,b) if ep['v']<0]
    report={'created_at':time.time(),'parameters':params,'candidates':CONFIGS,'training_negative_endpoints':len(speeds),
       'training_negative_speed_quantiles':np.quantile(speeds,[0,.5,.95]).tolist(),'validation_masks':len(validation),
       'selection_rule':'Maximize acceptance with no lost strict cases; newly accepted validation MAE <= 3m, speed MAE <=1m/s, p95 case MAE <=10m. Ties choose smaller correction bound.',
       'test_period':'2026-11-13 17:00-18:00 America/New_York, unused second PM hour; exclude IDs occurring in prior PM hour',
       'source_sha256':{'am':hashlib.sha256(Path(am).read_bytes()).hexdigest()},'gap_seconds':GAPS}
    report['validation'],_=evaluate(validation,{'strict':None,**CONFIGS},params,folder/'validation-cases.json')
    passing=[]
    for name in CONFIGS:
        row=report['validation'][name];new=row['newly_accepted']
        if new['n']>=10 and row['lost_strict_cases']==0 and new['mae_m']<=3 and new['speed_mae_mps']<=1 and new['p95_case_mae_m']<=10:passing.append(name)
    selected=max(passing,key=lambda m:(report['validation'][m]['accepted'],-CONFIGS[m]['negative_speed_limit_mps'])) if passing else 'strict'
    report.update(selected=selected,selected_config=CONFIGS.get(selected),state='selection_frozen');save(folder/'selection.json',report);print('FROZEN',selected,flush=True)
    # The untouched period is first read for scoring only after model selection.
    prior=json.loads(Path(previous_pm).read_text());seen={(s['id'],*tr['source_key'][:2]) for s in prior['sites'] for tr in s['tracks']}
    fresh=json.loads(Path(test).read_text());all_rows=cases(fresh,'test',10000);fresh_sites=[]
    for s in fresh['sites']:
        fresh_sites.append(dict(s,tracks=[tr for tr in s['tracks'] if (s['id'],*tr['source_key'][:2]) not in seen]))
    rows=cases(dict(fresh,sites=fresh_sites),'test',5)
    report['test_excluded_masks_seen_id']=sum(identity(r) in seen for r in all_rows)
    report['source_sha256']['test']=hashlib.sha256(Path(test).read_bytes()).hexdigest()
    report['test'],audit=evaluate(rows,{'strict':None,**({selected:CONFIGS[selected]} if selected!='strict' else {})},params,folder/'test-cases.json')
    report['test_snapshot_frames']=sum(s['frames'] for s in fresh['sites']);report['test_snapshot_fragments']=sum(len(s['tracks']) for s in fresh['sites'])
    report['test_rejections']=dict(Counter(x['results'][selected].get('reason','unknown') for x in audit if x['results'][selected]['state']!='candidate'))
    report['limitations']=['Retrospective same-intersection car masks; not vehicle identity validation between sensors.','Unused hour from same archival day, not independent-day validation.','Several masks can reuse a trajectory; counts are not independent vehicles.','Noise correction estimates endpoint velocity; positions remain exact. No observed records are edited.','Newly accepted cohorts must be assessed separately from unchanged strict successes.','Frozen near-stationary correction is not a general treatment of reversing vehicles, clocks, lane geometry or signal permissions.']
    report['state']='complete';save(folder/'report.json',report);print('DONE',folder,flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser()
    for arg in ('am','previous-pm','test','study','output'):p.add_argument('--'+arg,required=True)
    a=p.parse_args();run(a.am,a.previous_pm,a.test,a.study,a.output)
