"""Score a manually labelled review set; never auto-certify field validation.

Input JSON: {"cases":[{"id":"review-1","label":true,"detected":false,
"evidence":"independent video time range","note":"missed queue"}],
"threshold_revision":"rules-1 unchanged"}. Labels must cover selected negative
windows too; reviewing alerts alone cannot measure missed events.
"""
import argparse
import json


def review(data):
    counts=dict(tp=0,fp=0,fn=0,tn=0);seen=set()
    for case in data['cases']:
        if not case.get('id') or case['id'] in seen:raise ValueError('Unique case IDs required')
        seen.add(case['id'])
        if not isinstance(case.get('label'),bool) or not isinstance(case.get('detected'),bool):raise ValueError('Boolean label and detected required')
        if not case.get('evidence'):raise ValueError('Independent evidence reference required')
        name=('t' if case['label']==case['detected'] else 'f')+('p' if case['detected'] else 'n')
        counts[name]+=1
    return dict(counts,reviewed=len(seen),precision=counts['tp']/(counts['tp']+counts['fp']) if counts['tp']+counts['fp'] else None,
        recall=counts['tp']/(counts['tp']+counts['fn']) if counts['tp']+counts['fn'] else None,
        threshold_revision=data.get('threshold_revision','not recorded'),validation='provisional',
        note='Manual labels and representative sampling require review; these scores alone do not establish field validity.')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('labels');args=p.parse_args()
    with open(args.labels) as f:print(json.dumps(review(json.load(f)),indent=2))
