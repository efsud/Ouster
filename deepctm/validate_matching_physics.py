"""Per-site regression of final-physics screening; IDs used only for scoring."""
import argparse,json,time,hashlib
from pathlib import Path
from .archive_extension import association_groups
from .spatial_bridges import associate as existing
from .matching_physics import associate
from .reconstruction_layers import prediction

def run(source,study,output,limit=35):
    snapshot=json.loads(Path(source).read_text());report=json.loads(Path(study).read_text());params=report['calibration']['parameters'];groups=association_groups(snapshot,'test');records=[]
    for (site,direction,width),rows in sorted(groups.items()):
        # Hash sampling is independent of hidden identity matches; widths assigned
        # once per fragment in association_groups. Scenarios are correlated.
        rows=sorted(rows)[:limit]
        for scenario in ('complete','missing_both'):
            ai=[i for i,r in enumerate(rows) if scenario=='complete' or int(r[0][8:16],16)%5];bi=[i for i,r in enumerate(rows) if scenario=='complete' or int(r[0][16:24],16)%4][::-1]
            left=[rows[i][1] for i in ai];right=[rows[i][2] for i in bi]
            for method in ('current','screened'):
                matches=existing(left,right,method='feasible') if method=='current' else associate(left,right,params)
                accepted=[]
                for m in matches:
                    a,b=left[m['left']],right[m['right']]
                    # Both pipelines face identical actual final reconstruction.
                    if prediction(a,b,report,exact_join=True) is not None:accepted.append(m)
                correct=sum(ai[m['left']]==bi[m['right']] for m in accepted)
                records.append(dict(site=site,direction=direction,width=width,scenario=scenario,method=method,eligible=len(set(ai)&set(bi)),proposed=len(matches),matched=len(accepted),correct=correct,false=len(accepted)-correct,final_rejections=len(matches)-len(accepted)))
        print(site,direction,width,flush=True)
    def total(rows):
        sums={k:sum(r[k] for r in rows) for k in ('eligible','proposed','matched','correct','false','final_rejections')}
        sums['precision']=sums['correct']/sums['matched'] if sums['matched'] else None;sums['recall']=sums['correct']/sums['eligible'] if sums['eligible'] else None;return sums
    names={s['id']:s['name'] for s in snapshot['sites']}
    result={'created_at':time.time(),'source_sha256':hashlib.sha256(Path(source).read_bytes()).hexdigest(),'window':[snapshot['start'],snapshot['end']], 'parameters':params,
       'totals':{sc:{m:total([r for r in records if r['scenario']==sc and r['method']==m]) for m in ('current','screened')} for sc in ('complete','missing_both')},
       'sites':{site:{'name':name,'results':{sc:{m:total([r for r in records if r['site']==site and r['scenario']==sc and r['method']==m]) for m in ('current','screened')} for sc in ('complete','missing_both')}} for site,name in names.items()},'groups':records,
       'limitations':['Reused archival data: regression study, not a new untouched holdout.','Same-sensor spatial masks do not verify actual intersensor identities.','Hash sample of at most 35 fragments per site/direction/width; scenarios reuse tracks.','Both methods retain time, movement, speed, ambiguity and final reconstruction checks.']}
    Path(output).parent.mkdir(parents=True,exist_ok=True);Path(output).write_text(json.dumps(result,indent=2));print(result['totals'],flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--snapshot',required=True);p.add_argument('--study',required=True);p.add_argument('--output',required=True);a=p.parse_args();run(a.snapshot,a.study,a.output)
