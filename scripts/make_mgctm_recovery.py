"""Generate synthetic dated observations for an end-to-end calibration smoke run."""
from datetime import date,timedelta
import json
from pathlib import Path
import sys

from mgctm.cells import Network
from mgctm.demo import make
from mgctm.engine import run
from mgctm.experiments import parameterize
from mgctm.geometry import write_csv
from mgctm.trajectory_counts import FIELDS

out=Path(sys.argv[1])
out.mkdir(parents=True,exist_ok=False)
plan=dict(cases=[],scales={'count':10,'vehicles':5},bounds={'wave_mps_scale':[.7,1.3]},
          maxiter=1,screen=['E1-constant-demand','E2-constant-turns','E4-no-lost-time','E7-poisson'])
for i,split in enumerate(['train','validation','validation','test']):
    day=(date(2020,1,1)+timedelta(days=i)).isoformat()
    for peak in ('AM','PM'):
        spec=make(2,peak,duration=360)
        for r in spec['origins'][0]['demand_vph']:
            r[1]*=.93+.05*i
        target=out/f'{day}-{peak}.json'
        target.write_text(json.dumps(spec))
        observations=out/f'{day}-{peak}.csv'
        values,_,_=run(Network(parameterize(spec,{'wave_mps_scale':1.12})))
        write_csv(observations,(dict(date=day,peak=peak,end_s=t,target=name,metric=metric,
            value=rows[name,metric],source='SYNTHETIC generator; never a field observation')
            for t,rows in values.items() for name,metric in [('S1-L','count'),('S1-left','vehicles')]),FIELDS)
        plan['cases'].append(dict(date=day,peak=peak,split=split,network=target.name,observations=observations.name))
(out/'plan.json').write_text(json.dumps(plan,indent=2))
