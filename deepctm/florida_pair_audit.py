"""Readable all-Florida audit: actual links are hypotheses, masks have truth."""
import json,time
from pathlib import Path
from .reconstruction_study import summarize

ROOT=Path(__file__).resolve().parents[1]
def build(snapshot,layers):
    rows=json.loads((ROOT/'data/reconstruction/endpoint-speed/evaluation/test-cases.json').read_text())
    selected=json.loads((ROOT/'config/reconstruction/florida-endpoint-speed.json').read_text())
    site_results=[]
    for site in snapshot['sites']:
        cases=[r for r in rows if r['site']==site['id']];methods={}
        for method in ('strict','noise_0.1'):
            scored=[r['results'][method]['metrics'] for r in cases if r['results'][method]['state']=='candidate']
            methods[method]={'eligible':len(cases),'accepted':len(scored),'metrics':summarize(scored)}
        new=[r['results']['noise_0.1']['metrics'] for r in cases if r['results']['strict']['state']!='candidate' and r['results']['noise_0.1']['state']=='candidate']
        site_results.append(dict(id=site['id'],name=site['name'],correction_enabled=site['id'] not in selected.get('excluded_sites',[]),methods=methods,new_cases=summarize(new),live_corrected=sum(bool(p.get('endpoint_corrections')) and p['site']==site['id'] for p in layers['within_intersection'])))
    links=[]
    for row in layers.get('association_diagnostics',[]):
        actual=[p for p in layers['between_intersections'] if p['sites']==row['sites'] and p['direction']==row['direction']]
        links.append(dict(row,displayed_matches=len(actual),final_rejections=row['proposed_matches']-len(actual),
                          unmatched_displayed_departures=row['departure_candidates']-len(actual),unmatched_displayed_arrivals=row['arrival_candidates']-len(actual)))
    return dict(created_at=time.time(),snapshot_generated_at=snapshot['generated_at'],start=snapshot['start'],end=snapshot['end'],
        site_validation=site_results,links=links,
        note='All seven Florida intersections; all six adjacent pairs, both directions. Endpoint correction is local. Cross-sensor paths remain unverified hypotheses. Unmatched counts are fragments, not missing unique vehicles.')
if __name__=='__main__':
    snapshot=json.loads((ROOT/'data/florida-rolling/snapshot.json').read_text());layers=json.loads((ROOT/'data/reconstruction/word-v1-collection/layers.json').read_text())
    output=ROOT/'data/reconstruction/all-florida';output.mkdir(exist_ok=True,parents=True);(output/'pair-audit.json').write_text(json.dumps(build(snapshot,layers),indent=2))
