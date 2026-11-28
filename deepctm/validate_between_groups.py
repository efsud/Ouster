"""Recorded spatial-mask evaluation for independently clustered group priors.

The hidden strip is removed from ALL grouping inputs, before any group is built.
Local identity labels enter only distinct-donor counts and final evaluation; the
matcher cannot compare a departure identity with an arrival identity.
"""
import argparse
from dataclasses import asdict
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import time
import numpy as np
from .between_group_matching import associate, VERSION
from .bidirectional_association import motion_context
from .validate_spatial import masked
from .corridor_campaign import subset, earlier_ids, identity, atomic
from .reconstruction_layers import prediction


def visible_track(track, endpoint, exit_side):
    """Build a feature record solely from one observed side of a hidden strip."""
    points=np.asarray(track['points'],float)
    keep=points[:,0]<=endpoint['t'] if exit_side else points[:,0]>=endpoint['t']
    p=points[keep]
    result={k:track[k] for k in ('source_key','class_type','direction')}
    result['points']=p.tolist()
    if len(track.get('dimensions',[]))==len(points):
        result['dimensions']=np.asarray(track['dimensions'])[keep].tolist()
    # Full-track movement and lateral summaries can span the hidden strip.
    # Retain only the observed-side contexts; no interpolation across the mask.
    times={float(t) for t in p[:,0]}
    lateral=[]
    for key in ('lateral_start_context','lateral_end_context'):
        lateral.extend(q for q in track.get(key,[]) if float(q[0]) in times)
    if lateral:
        lateral=sorted({float(q[0]):q for q in lateral}.values())
        result['lateral_start_context']=lateral[:5]
        result['lateral_end_context']=lateral[-5:]
        result['lateral_start_m']=float(lateral[0][1])
        result['lateral_end_m']=float(lateral[-1][1])
    return result


def cases(snapshot, limit):
    for site in snapshot['sites']:
        for direction in ('eastbound','westbound'):
            for width in (20,50,100):
                rows=[]
                for tr in site['tracks']:
                    if tr['class_type']!='2' or tr['direction']!=direction:
                        continue
                    key=identity(site,tr)
                    if key is None:
                        continue
                    m=masked(tr,site['station_m'],width)
                    if m is None:
                        continue
                    a,b,truth=m[:3]
                    lt=visible_track(tr,a,True); rt=visible_track(tr,b,False)
                    a=dict(a,class_type='2',local_identity=key,
                           motion_context=motion_context(lt['points'],True))
                    b=dict(b,class_type='2',local_identity='arrival:'+key,
                           motion_context=motion_context(rt['points'],False))
                    rows.append((hashlib.sha256(key.encode()).hexdigest(),a,b,truth,lt,rt))
                rows.sort(key=lambda r:r[1]['t'])
                begin=max(0,(len(rows)-limit)//2)
                rows=rows[begin:begin+limit]
                if len(rows)>=4:
                    yield site,direction,width,rows


def evaluate(snapshot,report,weight,limit=60):
    from .trajectory_groups import group
    records=[]; details=[]
    totals={method:dict(eligible=0,correct=0,false=0,added_correct=0,added_false=0,
                        final_rejections=0,grouped_departures=0,grouped_arrivals=0,
                        anchor_matches=0,eligible_group_edges=0,position_errors_m=[])
            for method in ('baseline','group_candidate')}
    for site,direction,width,rows in cases(snapshot,limit):
        for scenario in ('complete','missing_endpoints'):
            ai=[i for i,r in enumerate(rows) if scenario=='complete' or int(r[0][8:16],16)%5]
            bi=[i for i,r in enumerate(rows) if scenario=='complete' or int(r[0][16:24],16)%4][::-1]
            # Independent clusters, freshly built from only the endpoints present
            # in this scenario. No removed endpoint can influence cohort evidence.
            ls=dict(id=site['id']+':upstream',station_m=site['station_m'],tracks=[rows[i][4] for i in ai])
            rs=dict(id=site['id']+':downstream',station_m=site['station_m'],tracks=[rows[i][5] for i in bi])
            lg=group(ls);rg=group(rs)
            left=[dict(rows[i][1],trajectory_group=lg['assignments'][k]) for k,i in enumerate(ai)]
            right=[dict(rows[i][2],trajectory_group=rg['assignments'][k]) for k,i in enumerate(bi)]
            for method,w in [('baseline',0),('group_candidate',weight)]:
                diag={}; matches=associate(left,right,report['calibration']['parameters'],weight=w,diagnostics=diag)
                rec=dict(site=site['id'],direction=direction,width_m=width,scenario=scenario,method=method,
                         eligible=len(set(ai)&set(bi)),correct=0,false=0,added_correct=0,added_false=0,final_rejections=0,
                         grouped_departures=sum(v is not None for v in lg['assignments']),
                         grouped_arrivals=sum(v is not None for v in rg['assignments']),
                         anchor_matches=diag.get('anchor_matches',0),eligible_group_edges=diag.get('eligible_group_edges',0))
                errors=[]
                for m in matches:
                    i,j=ai[m['left']],bi[m['right']]
                    p=prediction(rows[i][1],rows[j][2],report,exact_join=True)
                    if p is None:
                        rec['final_rejections']+=1;continue
                    correct=rows[i][0]==rows[j][0]
                    rec['correct' if correct else 'false']+=1
                    if m.get('group_assistance'):
                        rec['added_correct' if correct else 'added_false']+=1
                    error=None
                    if correct:
                        q=np.asarray(p);truth=rows[i][3]
                        error=float(np.mean(abs(np.interp(truth[:,0],q[:,0],q[:,1])-truth[:,1])))
                        errors.append(error)
                    details.append(dict(site=site['id'],direction=direction,width_m=width,scenario=scenario,method=method,
                                        departure_hash=rows[i][0],arrival_hash=rows[j][0],correct=correct,
                                        group_assistance=bool(m.get('group_assistance')),position_mae_m=error))
                for k in totals[method]:
                    if k!='position_errors_m':totals[method][k]+=rec[k]
                totals[method]['position_errors_m'].extend(errors)
                records.append(rec)
    for stats in totals.values():
        errors=stats.pop('position_errors_m')
        stats['position_mae_m']=float(np.mean(errors)) if errors else None
        stats['p95_case_mae_m']=float(np.quantile(errors,.95)) if errors else None
        stats['precision']=stats['correct']/max(1,stats['correct']+stats['false'])
    return dict(totals=totals,groups=records,matches=details)


def run(source,report_path,output,weight=.25,limit=60):
    from .trajectory_groups import GroupConfig, VERSION as GROUPING_VERSION
    raw=Path(source).read_bytes();snapshot=json.loads(raw);report=json.loads(Path(report_path).read_text())
    folder=Path(output);folder.mkdir(parents=True,exist_ok=True)
    duration=snapshot['end']-snapshot['start'];boundary=duration/2
    protocol=dict(created_at=time.time(),version=VERSION,source_sha256=hashlib.sha256(raw).hexdigest(),
                  window=[snapshot['start'],snapshot['end']],split_absolute=snapshot['start']+boundary,
                  embargo_s=30,weight=weight,limit_per_mask_pool=limit,parameters=report['calibration']['parameters'],
                  grouping_version=GROUPING_VERSION,grouping_config=asdict(GroupConfig()),
                  candidate_identity_exclusion='all same-local-ID fragments, both sides',
                  method='Independent observed-fragment groups, >=3 other baseline anchors, nonnegative timing penalty; baseline retained',
                  hidden_information_policy='Remove whole strip from every grouping feature; removed endpoints excluded before grouping; full-track movement/lateral summaries removed.',
                  decision_rule='Any gain in correct matches and no added false matches in early and later partitions. No tuning on later results.',
                  test_opened=False)
    atomic(folder/'protocol.json',protocol)
    validation=subset(snapshot,0,boundary-30)
    test=subset(snapshot,boundary+30,duration,earlier_ids(snapshot,boundary))
    v=evaluate(validation,report,weight,limit);atomic(folder/'validation.json',v)
    print(json.dumps(dict(stage='validation',totals=v['totals'])),flush=True)
    vb,vc=v['totals']['baseline'],v['totals']['group_candidate']
    eligible=vc['correct']>vb['correct'] and vc['false']<=vb['false']
    protocol.update(test_opened=True,validation_qualified=eligible,selection_frozen_at=time.time())
    atomic(folder/'protocol.json',protocol)
    t=evaluate(test,report,weight,limit);atomic(folder/'test.json',t)
    tb,tc=t['totals']['baseline'],t['totals']['group_candidate']
    deploy=eligible and tc['correct']>tb['correct'] and tc['false']<=tb['false']
    result=dict(state='complete',protocol=protocol,validation=v['totals'],test=t['totals'],deployment_eligible=deploy,
                qualification='spatial_mask_proxy_only',field_validated=False,
                limitations=['Spatial masking within individual sensors is a proxy, not cross-sensor identity validation.',
                             'No raw unobserved roadway truth; group agreement cannot prove individual identity.',
                             'Several masks and scenarios reuse vehicles; cases are not statistically independent.',
                             'The later half-hour excludes all identities seen earlier, but is not an independent day.',
                             'Groups need overlap in visible paths; sparse or stopped clusters may remain unassigned.',
                             'Baseline anchors are estimated assignments, not known identities.'])
    atomic(folder/'report.json',result);print(json.dumps(result),flush=True)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--snapshot',required=True);p.add_argument('--report',required=True)
    p.add_argument('--output',required=True);p.add_argument('--weight',type=float,default=.25);p.add_argument('--limit',type=int,default=60)
    args=p.parse_args();run(args.snapshot,args.report,args.output,args.weight,args.limit)
