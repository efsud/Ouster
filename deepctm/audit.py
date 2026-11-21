"""Read-only receipt continuity audit; event coverage is not FRAME validity."""
import argparse
import itertools
import json
from pathlib import Path
import sqlite3


def audit(database,sites):
    result={}
    with sqlite3.connect('file:'+str(Path(database).resolve())+'?mode=ro',uri=True) as db:
        for site in sites:
            bins={};previous=None;count=0
            for (t,) in db.execute('SELECT received_at FROM raw_events INDEXED BY raw_site_receipt WHERE site=? ORDER BY received_at',(site,)):
                count+=1;k=int(t//900);bins.setdefault(k,0.)
                if previous is not None and 0<t-previous<=3:
                    for j in range(int(previous//900),k+1):bins[j]=bins.get(j,0)+max(0,min(t,(j+1)*900)-max(previous,j*900))
                previous=t
            result[site]={'events':count,'coverage_seconds':bins,'valid_bins':sum(v>=720 for v in bins.values())}
    pairs=[]
    for a,b in itertools.combinations(sites,2):
        common=sorted(k for k,v in result[a]['coverage_seconds'].items() if v>=720 and result[b]['coverage_seconds'].get(k,0)>=720)
        longest=run=0;last=None
        for k in common:run=run+1 if last==k-1 else 1;longest=max(longest,run);last=k
        pairs.append({'sites':[a,b],'overlapping_bins':len(common),'longest_bins':longest})
    return {'sites':result,'pairs':pairs,'definition':'15-minute receipt bins; >=80% coverage from intervals <=3 s; not proof of frame completeness or clock validity'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--database',default='data/ouster.sqlite3');p.add_argument('--output',default='data/deepctm/receipt-audit.json');a=p.parse_args()
    sites=[s['id'] for s in json.loads(Path('config/sites.json').read_text())['sites'] if s['region']=='Toronto']
    Path(a.output).write_text(json.dumps(audit(a.database,sites),indent=2))
