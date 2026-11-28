"""Reproducible one-factor screens, bounded calibration, and date-held-out selection."""
from copy import deepcopy
import json
from pathlib import Path
from time import perf_counter

import numpy as np
from .cells import Network
from .engine import run
from .evaluation import day_loss, match, paired_summary, select, summarize
from .inputs import load_observations, number

VARIANTS={'E0':[], 'E1-constant-demand':['constant_demand'],
          'E2-constant-turns':['constant_turns'], 'E3-infinite-bay':['infinite_bays'],
          'E4-no-lost-time':['no_lost'], 'E5-no-midblock':['no_midblock'],
          'E5-net-midblock':['net_midblock'], 'E6-protected-only':['protected_only'],
          'E7-poisson':['poisson'], 'E8-alternate-signals':['alternate_signals'],
          'E9-half-step':['half_step'],'E9-coarse-cells':['coarse_cells']}


def average(rows,duration):
    x=0.
    for i,(t,v) in enumerate(rows):
        nxt=rows[i+1][0] if i+1<len(rows) else duration
        x+=max(0,min(nxt,duration)-t)*v
    return x/duration


def constant_turns(rows,duration):
    return [[0,{k:average([[t,r[k]] for t,r in rows],duration) for k in rows[0][1]}]]


def net_midblock(spec):
    origins=[o for o in spec['origins'] if o.get('midblock')]
    exits=spec.get('withdrawals',[])
    by_key={}
    for kind,items in (('entry',origins),('exit',exits)):
        for item in items:
            key=item.get('midblock_key')
            if not key or kind in by_key.setdefault(key,{}):
                raise ValueError('Net-flow variant needs explicit unique midblock_key pairs')
            by_key[key][kind]=item
    spec['origins']=[o for o in spec['origins'] if not o.get('midblock')]
    spec['withdrawals']=[]
    sections={s['id']:s for s in spec['sections']}
    for pair in by_key.values():
        o,e=pair.get('entry'),pair.get('exit')
        if not o or not e:
            if o: spec['origins'].append(o)
            if e: spec['withdrawals'].append(e)
            continue
        a,b=sections[e['from']],sections[o['to']]
        if a['link']!=b['link'] or abs(a['end_m']-b['start_m'])>1e-6:
            raise ValueError('Net flow requires collocated entries and withdrawals')
        from .inputs import Series
        x=Series.from_rows(o['demand_vph']);y=Series.from_rows(e['rate_vph'])
        ts=sorted(set(x.times+y.times))
        o['demand_vph']=[[t,max(0,x.at(t)-y.at(t))] for t in ts]
        e['rate_vph']=[[t,max(0,y.at(t)-x.at(t))] for t in ts]
        spec['origins'].append(o)
        spec['withdrawals'].append(e)


def variant(source, flags):
    spec=deepcopy(source)
    if 'constant_demand' in flags:
        for o in spec['origins']:
            o['demand_vph']=[[0,average(o['demand_vph'],spec['duration_s'])]]
    if 'constant_turns' in flags:
        for o in spec['origins']:
            o['ratios']=constant_turns(o['ratios'],spec['duration_s'])
        for e in spec['connections']:
            if 'next_ratios' in e: e['next_ratios']=constant_turns(e['next_ratios'],spec['duration_s'])
    for e in spec['connections']:
        if 'signal' not in e: continue
        if 'alternate_signals' in flags:
            if 'comparison_signal' not in e:
                raise ValueError('E8 requires a supplied alternative plan on every signal movement')
            e['signal']=deepcopy(e['comparison_signal'])
        if 'no_lost' in flags: e['signal']['lost_s']=0
        if 'protected_only' in flags:
            e['signal']['changes']=[[t,'red' if mode in ('permissive','rtor') else mode]
                                      for t,mode in e['signal']['changes']]
    if 'no_midblock' in flags:
        spec['origins']=[o for o in spec['origins'] if not o.get('midblock')]
        spec['withdrawals']=[]
    if 'net_midblock' in flags:
        net_midblock(spec)
    if 'half_step' in flags: spec['dt_s']=spec.get('dt_s',1)/2
    if 'coarse_cells' in flags: spec['min_cell_m']=spec.get('min_cell_m',15)*2
    return spec


def parameterize(source,params):
    spec=deepcopy(source)
    for s in spec['sections']:
        for key in ('vf_mps','wave_mps','jam_veh_per_m_lane'):
            s[key]*=params.get(key+'_scale',1)
    for e in spec['connections']:
        if 'signal' in e:
            if 'lost_s' in params and e['signal'].get('lost_s',0)>0:
                e['signal']['lost_s']=params['lost_s']
            if 'alternate_vph_scale' in params and 'alternate_vph' in e['signal']:
                e['signal']['alternate_vph']*=params['alternate_vph_scale']
    return spec


def predict(cases, flags, params):
    all_pairs=[]; diagnostics=[]
    for case in cases:
        source,obs=case['spec'],case['obs']
        start=perf_counter()
        values,meta,_=run(Network(parameterize(variant(source,flags),params)),
                        seed=case['seed'],stochastic='poisson' in flags,
                        infinite_bays='infinite_bays' in flags)
        diagnostics.append(dict(date=case['date'],peak=case['peak'],runtime_s=perf_counter()-start,**meta))
        all_pairs.extend(match(values,obs))
    return all_pairs, diagnostics


def fit(cases, flags, bounds, scales, budget):
    from scipy.optimize import differential_evolution
    names=list(bounds)
    supported={x+'_scale' for x in ('vf_mps','wave_mps','jam_veh_per_m_lane','alternate_vph')}|{'lost_s'}
    if not set(names)<=supported:
        raise ValueError('Unknown calibration parameter')
    if not names:
        return {}
    if any(not np.isfinite([a,b]).all() or a>=b or a<(0 if k=='lost_s' else 1e-6)
           for k,(a,b) in bounds.items()):
        raise ValueError('Invalid physical calibration bounds')
    def objective(x):
        rows,_=predict(cases,flags,dict(zip(names,x)))
        return float(np.mean(list(day_loss(rows,scales).values())))
    best=differential_evolution(objective,list(bounds.values()),maxiter=budget,popsize=5,
                               seed=42,polish=False)
    return dict(zip(names,map(float,best.x)))


def load_cases(plan,path):
    cases=[]
    for entry in plan['cases']:
        date=entry['date']; peak=entry['peak']; split=entry['split']
        if split not in ('train','validation','test'):
            raise ValueError('Invalid date partition')
        spec=json.loads((path/entry['network']).read_text())
        if peak!=spec['peak']:
            raise ValueError('Peak profile mismatch')
        obs=[r for r in load_observations(path/entry['observations']) if r['date']==date and r['peak']==peak]
        if not obs:
            raise ValueError(f'Missing independent observations: {date} {peak}')
        cases.append(dict(date=date,peak=peak,split=split,spec=spec,obs=obs,seed=int(entry.get('seed',42))))
    if len({(c['date'],c['peak']) for c in cases})!=len(cases):
        raise ValueError('Duplicate date/peak case')
    if len({c['spec']['synthetic'] for c in cases})!=1:
        raise ValueError('Never mix synthetic and field observations')
    date_sets=[{c['date'] for c in cases if c['split']==split} for split in ('train','validation','test')]
    if not all(date_sets) or not max(date_sets[0])<min(date_sets[1]) or not max(date_sets[1])<min(date_sets[2]):
        raise ValueError('Train, validation and test must be nonempty, chronological and disjoint by date')
    return cases


def execute(planfile,out):
    planfile=Path(planfile); plan=json.loads(planfile.read_text())
    cases=load_cases(plan,planfile.parent)
    train,validation,test=([c for c in cases if c['split']==s] for s in ('train','validation','test'))
    scales={k:number(v,'metric scale',1e-9) for k,v in plan['scales'].items()}
    bounds=plan.get('bounds',{})
    budget=int(plan.get('maxiter',2))
    if budget<0: raise ValueError('Calibration budget must be nonnegative')
    # Low-cost one-at-a-time sensitivity at bounded midpoints; screening only,
    # not a global Morris estimate or a replacement for calibration.
    sensitivity={}
    if bounds and plan.get('screen_parameters'):
        center={k:(a+b)/2 for k,(a,b) in bounds.items()}
        for k,(a,b) in bounds.items():
            low,_=predict(train,[],{**center,k:a})
            high,_=predict(train,[],{**center,k:b})
            sensitivity[k]=dict(low=float(np.mean(list(day_loss(low,scales).values()))),
                                high=float(np.mean(list(day_loss(high,scales).values()))))
    params=fit(train,[],bounds,scales,budget)
    rows,meta=predict(validation,[],params)
    baseline=day_loss(rows,scales)
    screens={}; eligible={'E0':[]}
    for key in plan.get('screen',[]):
        if key=='E0': continue
        flags=VARIANTS[key]
        try:
            rows,meta=predict(validation,flags,params)
            loss=day_loss(rows,scales)
        except ValueError as exc:
            screens[key]={'state':'not_applicable','reason':str(exc)}
            continue
        by_peak={p:paired_summary({k:v for k,v in baseline.items() if k[1]==p},
                                  {k:v for k,v in loss.items() if k[1]==p})
                 for p in {k[1] for k in baseline}}
        screens[key]=dict(by_peak=by_peak,metrics=summarize(rows),diagnostics=meta)
        if any(v['mean_delta'] < -1e-9 for v in by_peak.values()):
            eligible[key]=flags
    for key in plan.get('interactions',[]):
        if len(key)!=2 or len(set(key))!=2:
            raise ValueError('Interactions must be pairs')
        if all(k in eligible and k!='E0' for k in key):
            eligible['+'.join(key)]=[flag for k in key for flag in eligible[k]]
    results={}; parameters={}; selections={}
    for peak in sorted({c['peak'] for c in validation}):
        tr=[c for c in train if c['peak']==peak]; va=[c for c in validation if c['peak']==peak]
        te=[c for c in test if c['peak']==peak]
        if not tr or not te: raise ValueError(f'Incomplete date partitions for {peak}')
        losses={};results[peak]={};parameters[peak]={}
        for key, flags in eligible.items():
            parameters[peak][key]=fit(tr,flags,bounds,scales,budget)
            rows,meta=predict(va,flags,parameters[peak][key])
            losses[key]=day_loss(rows,scales)
            results[peak][key]=dict(validation_loss=float(np.mean(list(losses[key].values()))),
                                    metrics=summarize(rows),diagnostics=meta)
        complexity={k:sum(flag not in {'constant_demand','constant_turns','no_midblock','net_midblock',
                    'no_lost','protected_only'} for flag in f)-
                    sum(flag in {'constant_demand','constant_turns','no_midblock','net_midblock',
                    'no_lost','protected_only'} for flag in f) for k,f in eligible.items()}
        decision=select(losses,complexity)
        if (key:=decision['selected']) is not None:
            rows,meta=predict(te,eligible[key],parameters[peak][key])
            decision.update(test_metrics=summarize(rows),test_diagnostics=meta)
        selections[peak]=decision
    for entry in screens.values():
        if 'by_peak' in entry:
            entry['lower_point_loss']=sorted(p for p,v in entry['by_peak'].items() if v['mean_delta'] < -1e-9)
    report=dict(synthetic=cases[0]['spec']['synthetic'],initial_parameters=params,
                parameter_sensitivity=sensitivity,screen=screens,recalibration=parameters,
                validation=results,selection=selections,
                overall_selection={p:r['selected'] for p,r in selections.items()},
                seeds={f"{c['date']} {c['peak']}":c['seed'] for c in cases},
                calibration_maxiter=budget)
    Path(out).mkdir(parents=True,exist_ok=True)
    (Path(out)/'experiment.json').write_text(json.dumps(report,indent=2,allow_nan=False))
    from .geometry import write_csv
    comparison=[dict(variant=k,peak=p,days=v['days'],mean_delta=v['mean_delta'],
                     ci_low=v['ci95'][0] if v['ci95'] else '',
                     ci_high=v['ci95'][1] if v['ci95'] else '')
                for k,r in screens.items() for p,v in r.get('by_peak',{}).items()]
    if comparison:
        write_csv(Path(out)/'feature-comparison.csv',comparison)
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig,ax=plt.subplots(figsize=(10, max(3,len(comparison)*.35)),layout='constrained')
        y=np.arange(len(comparison))
        ax.barh(y,[r['mean_delta'] for r in comparison])
        ax.set_yticks(y,[f"{r['peak']} {r['variant']}" for r in comparison])
        ax.axvline(0,color='#333')
        ax.set(xlabel='Paired validation loss difference vs E0 (lower is better)',
               title=('SYNTHETIC · ' if report['synthetic'] else '')+'Movement-group CTM feature screen')
        fig.savefig(Path(out)/'feature-comparison.png',dpi=140)
        plt.close(fig)
    return report
