"""Overlay audited field input tables on an explicitly verified geometry."""
from collections import defaultdict
from copy import deepcopy
import csv

from .inputs import number


def overlay(spec, csv_path):
    spec=deepcopy(spec)
    edges={x['id']:x for x in spec['connections']}
    origins={x['id']:x for x in spec['origins']}
    exits={x['id']:x for x in spec.get('withdrawals',[])}
    rows=defaultdict(dict)
    sources=set()
    with open(csv_path,newline='') as stream:
        for r in csv.DictReader(stream):
            if not r['source'].strip():
                raise ValueError('Each field profile row needs provenance')
            sources.add(r['source'])
            key=(r['kind'],r['target'])
            t=number(r['start_s'],'interval start')
            if t in rows[key]:
                raise ValueError(f'Duplicate profile time for {key}')
            rows[key][t]=r['value']
    required={(kind,k) for k in origins for kind in ('demand_vph','origin_turns')}
    required|={('midblock_exit_vph',k) for k in exits}
    required|={('signal_state',k) for k,e in edges.items() if 'signal' in e}
    required|={('next_turns',k) for k,e in edges.items() if 'signal' in e and e.get('to')}
    required|={('capacity_vph',k) for k,e in edges.items() if 'capacity_vph' in e}
    if set(rows)!=required:
        raise ValueError(f'Profile coverage mismatch: missing {sorted(required-set(rows))}; extra {sorted(set(rows)-required)}')
    for (kind,k), values in rows.items():
        if max(values)>=spec['duration_s'] or min(values)!=0:
            raise ValueError('Every profile must start at zero and end within the window')
        def turns(raw):
            import json
            return json.loads(raw)
        parser=turns if kind.endswith('_turns') else str if kind=='signal_state' else float
        series=[[t,parser(v)] for t,v in sorted(values.items())]
        if kind=='demand_vph': origins[k]['demand_vph']=series
        elif kind=='origin_turns': origins[k]['ratios']=series
        elif kind=='next_turns': edges[k]['next_ratios']=series
        elif kind=='capacity_vph': edges[k]['capacity_vph']=series
        elif kind=='midblock_exit_vph': exits[k]['rate_vph']=series
        elif kind=='signal_state':
            e=edges[k]['signal']
            e.pop('cycle_s',None);e.pop('offset_s',None)
            e.update(changes=series,valid_until_s=spec['duration_s'])
    spec['input_sources']=sorted(sources)
    return spec
