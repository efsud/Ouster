"""Compare association algorithms using known identities hidden behind spatial masks."""
import argparse,hashlib,json,time
from pathlib import Path
from .validate_spatial import masked
from .spatial_bridges import associate
from .local_gaps import VEHICLES

def run(snapshot,output,partition="late"):
    if partition not in ("early","late"):raise ValueError("Invalid partition")
    raw=Path(snapshot).read_bytes();s=json.loads(raw);groups=[]
    for site in s['sites']:
        for direction in ('eastbound','westbound'):
            for width in (20,50,100):
                cases=[]
                for tr in site['tracks']:
                    if tr['class_type'] not in VEHICLES or tr['direction']!=direction:continue
                    m=masked(tr,site['station_m'],width)
                    if m is None:continue
                    duration=s['end']-s['start']
                    if partition=='late' and m[3]<.8*duration:continue
                    if partition=='early' and m[4]>.2*duration:continue
                    a,b,truth,begin,end=m
                    a.update(class_type=tr['class_type']);b.update(class_type=tr['class_type']);cases.append((a,b))
                for scenario in ('complete','missing_arrivals','missing_departures','missing_both'):
                    ai=[i for i in range(len(cases)) if 'departures' not in scenario and scenario!='missing_both' or i%5!=0]
                    bi=[i for i in range(len(cases)) if 'arrivals' not in scenario and scenario!='missing_both' or i%4!=0]
                    # Reverse input order to prevent list order serving as an identity cue.
                    bi.reverse();metrics={}
                    for method in ('legacy','residual','augmented'):
                        matches=associate([cases[i][0] for i in ai],[cases[i][1] for i in bi],method=method)
                        correct=sum(ai[m['left']]==bi[m['right']] for m in matches)
                        metrics[method]={'matched':len(matches),'correct':correct,'false':len(matches)-correct,'later_rounds':sum(m.get('assignment_round',1)>1 for m in matches)}
                    groups.append(dict(site=site['id'],direction=direction,width=width,scenario=scenario,eligible=len(set(ai)&set(bi)),metrics=metrics))
    totals={}
    for scenario in ('complete','missing_arrivals','missing_departures','missing_both'):
        totals[scenario]={}
        selected=[g for g in groups if g['scenario']==scenario]
        for method in ('legacy','residual','augmented'):
            v={key:sum(g['metrics'][method][key] for g in selected) for key in ('matched','correct','false','later_rounds')}
            v['eligible']=sum(g['eligible'] for g in selected);v['precision']=v['correct']/v['matched'] if v['matched'] else None;v['recall']=v['correct']/v['eligible'] if v['eligible'] else None;totals[scenario][method]=v
    report=dict(partition=partition,created_at=time.time(),source_sha256=hashlib.sha256(raw).hexdigest(),source_window=[s['start'],s['end']],totals=totals,groups=groups,limitations=['Disjoint chronological 20% partition; known identities hidden from matcher. Late partition was used during development.','Widths and missing-data scenarios overlap; counts are not independent vehicles.','Same-sensor masking does not validate cross-sensor identity, clocks, or road alignment.','Residual rounds depend on earlier estimated assignments.'])
    Path(output).parent.mkdir(parents=True,exist_ok=True);Path(output).write_text(json.dumps(report,indent=2));return report
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--partition',choices=['early','late'],default='late');p.add_argument('--snapshot',required=True);p.add_argument('--output',required=True);a=p.parse_args();print(json.dumps(run(a.snapshot,a.output,a.partition)['totals'],indent=2))
