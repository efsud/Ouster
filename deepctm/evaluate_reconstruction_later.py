"""Frozen later-period evaluation; no fitting or method selection here."""
import argparse,hashlib,json,time
from pathlib import Path
import numpy as np
from .reconstruction_study import masked_case,metrics,summarize
from .trajectory_reconstruction import baseline,refine


def run(source,study,output,limit_per_stratum=20):
    raw=Path(source).read_bytes();snapshot=json.loads(raw);report=json.loads(Path(study).read_text())
    if report.get('state')!='evaluated_ablation':raise ValueError('Completed frozen study required')
    if snapshot['start']<=report['source_window'][1]+30:raise ValueError('Later window overlaps original study')
    params=report['calibration']['parameters'];winner=report['selected_method'];methods=list(dict.fromkeys(['M1_linear','M1_hermite',winner]));groups={}
    for site in snapshot['sites']:
        # Preserve the original test areas; no development sites contaminate this test.
        if site['id'] not in report['plan']['spatial_partitions']['test']:continue
        for tr in site['tracks']:
            if tr['class_type']!='2' or tr.get('method'):continue
            for gap in report['plan']['gap_seconds']:
                case=masked_case(tr,gap)
                if case is None:continue
                key=json.dumps([site['id'],tr.get('source_key'),tr['points'][0][0],gap],sort_keys=True)
                rank=hashlib.sha256(key.encode()).hexdigest();stratum=(site['id'],tr['direction'],gap)
                groups.setdefault(stratum,[]).append((rank,case))
    scores={m:{} for m in methods};meta={};cases=[]
    for stratum,values in sorted(groups.items()):
        for rank,case in sorted(values,key=lambda v:v[0])[:limit_per_stratum]:cases.append((stratum,case))
    for cid,((site,direction,gap),(a,b,truth)) in enumerate(cases):
        meta[cid]=dict(site=site,direction=direction,gap_seconds=gap)
        for m in methods:
            p=baseline(a,b,'linear' if m=='M1_linear' else 'hermite')
            if m.startswith('kinematic_'):
                r=refine(a,b,p,**params,smoothness=float(m.split('_')[1]))
                if r['state']!='candidate':continue
                p=r['points']
            scores[m][cid]=metrics(p,truth,params)
    common=set.intersection(*(set(v) for v in scores.values()))
    result=dict(created_at=time.time(),source_sha256=hashlib.sha256(raw).hexdigest(),source_window=[snapshot['start'],snapshot['end']],frozen_study_sha256=hashlib.sha256(Path(study).read_bytes()).hexdigest(),selected_method=winner,
      sample_rule=f'Hash-selected at most {limit_per_stratum} cases per site/direction/gap; no selection by hidden outcomes',eligible_before_sampling=sum(map(len,groups.values())),sampled=len(cases),methods={})
    for m,rows in scores.items():
        result['methods'][m]={'accepted':len(rows),'common':summarize([rows[i] for i in common]),'by_gap_and_regime':{f'{gap}s_{name}':summarize([rows[i] for i in common if meta[i]['gap_seconds']==gap and rows[i]['moving']==moving]) for gap in report['plan']['gap_seconds'] for name,moving in [('moving',True),('stationary',False)]}}
    radius=report['uncertainty']['radius_m'];rows=list(scores[winner].values());result['frozen_uncertainty']={'radius_m':radius,'nominal':.9,'full_gap_coverage':sum(r['max_error_m']<=radius for r in rows)/len(rows) if rows else None}
    result['limitations']=['Frozen comparison on later time, original test areas only','Masks reuse vehicle fragments; sample is not independent vehicles','Same-sensor gaps do not validate inter-site identity or paths','No fitting or parameter selection performed on later errors']
    path=Path(output);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(result,indent=2,allow_nan=False));return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--snapshot',required=True);p.add_argument('--study',required=True);p.add_argument('--output',required=True);a=p.parse_args();r=run(a.snapshot,a.study,a.output);print(json.dumps({k:r[k] for k in ['sampled','methods','frozen_uncertainty']},indent=2))
