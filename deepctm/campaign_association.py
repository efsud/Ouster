"""Masked same-sensor association check; never a claim of cross-site identity truth."""
import time
from .archive_extension import association_groups
from .matching_physics import associate
from .spatial_bridges import associate as baseline
from .reconstruction_layers import prediction
from .matching_assignment import associate as global_associate

def evaluate(snapshot,params,deadline,limit=12):
    report={'selected_method':'kinematic_0.01','calibration':{'parameters':params}}
    records=[]
    for (site,direction,width),rows in sorted(association_groups(snapshot,'test').items()):
        if time.time()>=deadline:break
        rows=sorted(rows)[:limit]
        # Delete different endpoint subsets, retaining unmatched alternatives.
        ai=[i for i,r in enumerate(rows) if int(r[0][8:16],16)%5]
        bi=[i for i,r in enumerate(rows) if int(r[0][16:24],16)%4][::-1]
        left=[rows[i][1] for i in ai];right=[rows[i][2] for i in bi]
        for name,matcher in [('baseline',lambda a,b:baseline(a,b,method='feasible')),('physics_screened',lambda a,b:associate(a,b,params)),('global_partial',lambda a,b:global_associate(a,b,params))]:
            if time.time()>=deadline:break
            matches=matcher(left,right);accepted=[]
            for m in matches:
                if time.time()>=deadline:break
                if prediction(left[m['left']],right[m['right']],report,exact_join=True) is not None:accepted.append(m)
            correct=sum(ai[m['left']]==bi[m['right']] for m in accepted)
            records.append(dict(site=site,direction=direction,width=width,method=name,eligible=len(set(ai)&set(bi)),matched=len(accepted),correct=correct,false=len(accepted)-correct))
    totals={}
    for method in ('baseline','physics_screened','global_partial'):
        totals[method]={key:sum(r[key] for r in records if r['method']==method) for key in ('eligible','matched','correct','false')}
    return {'state':'complete' if time.time()<deadline else 'deadline_reached','totals':totals,'groups':records,
        'limitations':['Same-sensor blind spatial bands, not actual cross-sensor ground truth.','At most twelve fragments per site/direction/width; sampled scenarios are not independent.','Missing endpoints retained as unmatched alternatives.','No threshold selection on these test results.']}
