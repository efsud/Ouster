"""Spatial/time holdout comparison of identity-blind tracklet matching.

One spatial mask per observed car fragment, assigned by metadata hash. Original
identity is used only for scoring. Dropouts simulate missing observations, not
the full turning/occlusion process. Never deploy from this proxy test alone.
"""
import argparse
import hashlib
import json
import time
from pathlib import Path
from .reconstruction_study import partition_track
from .validate_spatial import masked
from .spatial_bridges import associate
from .global_association import associate_global


def totals(rows):
    result = {key: sum(r[key] for r in rows) for key in ('eligible','matched','correct','false')}
    result['precision'] = result['correct']/result['matched'] if result['matched'] else None
    result['recall'] = result['correct']/result['eligible'] if result['eligible'] else None
    return result


def run(source, output, config='config/reconstruction/florida-study.json'):
    raw = Path(source).read_bytes(); snapshot = json.loads(raw)
    plan = json.loads(Path(config).read_text()); groups = {}
    for site in snapshot['sites']:
        for track in site['tracks']:
            split = partition_track(site['id'],track,snapshot,plan)
            if split is None:
                continue
            identity = json.dumps([site['id'],track.get('source_key'),track['points'][0][0]])
            rank = hashlib.sha256(identity.encode()).hexdigest()
            width = (20,50,100)[int(rank[:8],16)%3]
            case = masked(track,site['station_m'],width)
            if case is None:
                continue
            a,b,*_ = case
            a = dict(a,class_type='2'); b = dict(b,class_type='2')
            groups.setdefault((split,site['id'],track['direction'],width),[]).append((rank,a,b))
    methods = ['augmented','feasible','global_0.25','global_0.5','global_1.0']
    report = dict(state='validation',created_at=time.time(),source_sha256=hashlib.sha256(raw).hexdigest(),
        source_window=[snapshot['start'],snapshot['end']],plan=plan,
        parameters={'max_edge_cost':1.5,'unmatched_per_endpoint':.75,'selection_min_matches':25,'selection_min_precision':.95},
        split_cases={s:sum(len(v) for k,v in groups.items() if k[0]==s) for s in ('train','validation','test')},
        training='Fixed physical/cost gates; no learned identity parameters. Train partition reserved for later calibration.',
        limitations=['One mask per fragment; multiple fragments may still belong to one vehicle',
          'Dropout scenarios reuse masks and are reported separately, not pooled as independent samples',
          'Same-sensor spatial masks do not validate actual cross-sensor identity, clock alignment or unobserved paths',
          'Global objective margin is not a calibrated probability; unmatched alternatives remain explicit'])
    output = Path(output); output.parent.mkdir(parents=True,exist_ok=True)
    if output.exists():
        raise FileExistsError('Preserve prior evaluation; use a new output path')
    def save():
        output.write_text(json.dumps(report,indent=2,allow_nan=False))
    def evaluate(split, choices):
        rows = []
        for (part,site,direction,width),cases in sorted(groups.items()):
            if part != split:
                continue
            cases = sorted(cases)
            for scenario in ('complete','missing_both'):
                ai = [i for i,(rank,_,_) in enumerate(cases) if scenario=='complete' or int(rank[8:16],16)%5]
                bi = [i for i,(rank,_,_) in enumerate(cases) if scenario=='complete' or int(rank[16:24],16)%4][::-1]
                for method in choices:
                    left = [cases[i][1] for i in ai]; right = [cases[i][2] for i in bi]
                    matches = associate(left,right,method=method) if method in ('augmented','feasible') else associate_global(left,right,margin=float(method.split('_')[1]))
                    correct = sum(ai[m['left']]==bi[m['right']] for m in matches)
                    rows.append(dict(site=site,direction=direction,width=width,scenario=scenario,method=method,
                        eligible=len(set(ai)&set(bi)),matched=len(matches),correct=correct,false=len(matches)-correct))
        return {scenario:{method:totals([r for r in rows if r['scenario']==scenario and r['method']==method]) for method in choices}
                for scenario in ('complete','missing_both')}, rows
    report['validation'],report['validation_groups'] = evaluate('validation',methods)
    eligible = [m for m in methods if all(report['validation'][s][m]['matched']>=25 and
                (report['validation'][s][m]['precision'] or 0)>=.95 for s in report['validation'])]
    winner = max(eligible,key=lambda m:(min(report['validation'][s][m]['recall'] or 0 for s in report['validation']),-methods.index(m))) if eligible else None
    report.update(selected_method=winner,state='selection_frozen'); save()
    # Test is never used to choose a different margin or algorithm.
    choices = list(dict.fromkeys(['augmented','feasible']+([winner] if winner else [])))
    report['test'],report['test_groups'] = evaluate('test',choices)
    report['state'] = 'proxy_evaluated' if winner else 'insufficient_validation_support'
    report['deployment'] = 'No production association change; proxy evidence only'
    save(); return report


if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('--snapshot',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();r=run(a.snapshot,a.output)
    print(json.dumps({k:r[k] for k in ('state','split_cases','selected_method','validation','test')},indent=2))
