"""Freeze selection on early data, test later identities, audit live rejection causes."""
import argparse,json,hashlib,time
from pathlib import Path
from collections import Counter,defaultdict
import numpy as np
from .bidirectional_association import associate,motion_context
from .shape_association import associate as reference
from .kinematic_gate import path
from .spatial_bridges import reconstruct,endpoint
from .validate_spatial import masked
from .corridor_campaign import subset,earlier_ids,identity,atomic
from .reconstruction_layers import prediction

def groups(snapshot):
    result=defaultdict(list)
    for site in snapshot['sites']:
        for tr in site['tracks']:
            if tr['class_type']!='2':continue
            points=np.asarray(tr['points'],float)
            if len(points)<12 or np.any(np.diff(points[:,0])<=0) or np.any(np.diff(points[:,0])>1.5):continue
            key=hashlib.sha256(identity(site,tr).encode()).hexdigest();rank=int(key[:8],16)
            width=(20,50,100)[rank%3];spatial=masked(tr,site['station_m'],width)
            gap=(5,15,30,60)[rank%4];mid=(points[0,0]+points[-1,0]-gap)/2
            before=points[points[:,0]<=mid];after=points[points[:,0]>=mid+gap]
            a=endpoint(before.tolist(),True) if len(before)>=5 else None
            b=endpoint(after.tolist(),False) if len(after)>=5 else None
            temporal=(a,b,points[(points[:,0]>a['t'])&(points[:,0]<b['t'])]) if a and b else None
            for kind,size,m in [('spatial',width,spatial),('temporal',gap,temporal)]:
                if not m or not len(m[2]):continue
                a,b,truth=m[:3];a=dict(a,class_type='2');b=dict(b,class_type='2')
                a['motion_context']=motion_context(points[points[:,0]<=a['t']],True)
                b['motion_context']=motion_context(points[points[:,0]>=b['t']],False)
                result[kind,site['id'],tr['direction'],size].append((key,a,b,truth))
    return result

def evaluate(snapshot,report,blends,limit=20):
    output=[];detail=[];cache={}
    for group,rows in sorted(groups(snapshot).items()):
        rows.sort(key=lambda r:r[1]['t']);middle=max(0,(len(rows)-limit)//2);rows=rows[middle:middle+limit]
        for scenario in ('complete','missing_endpoints'):
            ai=[i for i,r in enumerate(rows) if scenario=='complete' or int(r[0][8:16],16)%5]
            bi=[i for i,r in enumerate(rows) if scenario=='complete' or int(r[0][16:24],16)%4][::-1]
            left=[rows[i][1] for i in ai];right=[rows[j][2] for j in bi]
            for blend in blends:
                proposed=reference(left,right,report['calibration']['parameters'],weight=.5,path_gate=path) if blend==0 else associate(left,right,report['calibration']['parameters'],blend=blend)
                correct=wrong=rejected=0;errors=[]
                for match in proposed:
                    i,j=ai[match['left']],bi[match['right']];key=(*group,i,j)
                    if key not in cache:cache[key]=prediction(rows[i][1],rows[j][2],report,exact_join=True)
                    p=cache[key]
                    if p is None:rejected+=1;continue
                    if rows[i][0]==rows[j][0]:
                        correct+=1;q=np.asarray(p);truth=rows[i][3];err=float(np.mean(abs(np.interp(truth[:,0],q[:,0],q[:,1])-truth[:,1])));errors.append(err)
                    else:wrong+=1;err=None
                    detail.append(dict(kind=group[0],site=group[1],direction=group[2],size=group[3],scenario=scenario,blend=blend,departure=rows[i][0],arrival=rows[j][0],correct=rows[i][0]==rows[j][0],position_mae_m=err))
                output.append(dict(kind=group[0],site=group[1],direction=group[2],size=group[3],scenario=scenario,blend=blend,eligible=len(set(ai)&set(bi)),correct=correct,false=wrong,final_rejections=rejected,errors_m=errors))
    totals={}
    for blend in blends:
        totals[str(blend)]={}
        for kind in ('temporal','spatial'):
            rows=[r for r in output if r['blend']==blend and r['kind']==kind];errors=[e for r in rows for e in r['errors_m']]
            totals[str(blend)][kind]={k:sum(r[k] for r in rows) for k in ('eligible','correct','false','final_rejections')}
            totals[str(blend)][kind].update(position_mae_m=float(np.mean(errors)) if errors else None,p95_case_mae_m=float(np.percentile(errors,95)) if errors else None)
    return dict(totals=totals,groups=output,matches=detail)

def audit(snapshot,report):
    by_id={s['id']:s for s in snapshot['sites']};links=[]
    def matcher(left,right):
        diag={};matches=associate(left,right,report['calibration']['parameters'],blend=0,diagnostics=diag)
        final=0
        for m in matches:
            if prediction(left[m['left']],right[m['right']],report,exact_join=True) is None:final+=1
        links.append(dict(sites=[left[0]['site'],right[0]['site']] if left and right else [],**diag,final_curve_rejections=final))
        return matches
    # Match the production class filter exactly.
    snap=dict(snapshot,sites=[dict(s,tracks=[t for t in s['tracks'] if t['class_type']=='2']) for s in snapshot['sites']])
    r=reconstruct(snap,matcher=matcher)
    return dict(pair_funnels=links,coverage=[{k:v for k,v in l.items() if k!='paths'} for l in r['links']],note='Pair counts are alternatives, not missing vehicles; unmatched departures count fragments. Full actual sensor identity truth is unavailable.')

def run(source,report_path,folder):
    raw=Path(source).read_bytes();snapshot=json.loads(raw);report=json.loads(Path(report_path).read_text());folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    duration=snapshot['end']-snapshot['start'];boundary=duration/2
    protocol=dict(created_at=time.time(),source_sha256=hashlib.sha256(raw).hexdigest(),window=[snapshot['start'],snapshot['end']],split_absolute=snapshot['start']+boundary,embargo_s=30,blends=[.25,.5],parameters=report['calibration']['parameters'],selection='More correct matches overall, no increase in false matches in either task; otherwise keep baseline. Test must confirm same rule and at least 20 added correct matches overall before deployment.',test_opened=False)
    atomic(folder/'protocol.json',protocol)
    validation=subset(snapshot,0,boundary-30);test=subset(snapshot,boundary+30,duration,earlier_ids(snapshot,boundary))
    v=evaluate(validation,report,[0,.25,.5]);atomic(folder/'validation.json',v)
    base=v['totals']['0'];qualifying=[]
    for blend in (.25,.5):
        q=v['totals'][str(blend)]
        if all(q[k]['false']<=base[k]['false'] and q[k]['correct']>=base[k]['correct'] for k in base) and sum(q[k]['correct']-base[k]['correct'] for k in base)>0:qualifying.append(blend)
    winner=max(qualifying,key=lambda b:sum(v['totals'][str(b)][k]['correct'] for k in base)) if qualifying else 0
    protocol.update(selected_blend=winner,test_opened=True,selection_frozen_at=time.time());atomic(folder/'protocol.json',protocol)
    # Even if neither qualifies, test only the predeclared .25 diagnostic, never
    # reselect on test scores. It cannot be deployed without validation success.
    tested=winner or .25
    t=evaluate(test,report,[0,tested]);atomic(folder/'test.json',t)
    base=t['totals']['0'];q=t['totals'][str(tested)]
    deploy=bool(winner and all(q[k]['false']<=base[k]['false'] and q[k]['correct']>=base[k]['correct'] for k in base) and sum(q[k]['correct']-base[k]['correct'] for k in base)>=20)
    a=audit(snapshot,report);atomic(folder/'rejections.json',a)
    result=dict(state='complete',protocol=protocol,validation=v['totals'],test=t['totals'],deployment_eligible=deploy,limitations=['Only disjoint later half-hour with excluded earlier IDs; not independent days.','Same-sensor masked identities do not validate between-sensor matching.','Repeated masks/scenarios are correlated. Acceleration is trusted for only three seconds.','Production exact trajectory and physics gates are retained.'])
    atomic(folder/'report.json',result);print(json.dumps(result),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--snapshot',required=True);p.add_argument('--report',required=True);p.add_argument('--output',required=True);a=p.parse_args();run(a.snapshot,a.report,a.output)
