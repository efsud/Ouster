"""Spatial-mask benchmark: trajectory shape and identity-free association separately."""
import argparse,json,time,hashlib
from pathlib import Path
import numpy as np
from .spatial_bridges import endpoint,curve,associate,reconstruct
from .local_gaps import VEHICLES

def masked(tr,station,width):
    p=np.asarray(tr['points'],float);sign=1 if tr['direction']=='eastbound' else -1
    if len(p)<12 or np.any(np.diff(p[:,0])<=0) or np.any(np.diff(p[:,0])>1.5):return None
    x=(p[:,1]-station)*sign
    before=np.where(x<=-width/2)[0];after=np.where(x>=width/2)[0]
    if not len(before) or not len(after):return None
    i=before[-1];j=after[0]
    if i<4 or j+4>=len(p) or j-i<3:return None
    a=endpoint(p[i-4:i+1],True);b=endpoint(p[j:j+5],False)
    if a is None or b is None:return None
    return a,b,p[i+1:j],p[i-4,0],p[j+4,0]

def run(snapshot,output):
    raw=Path(snapshot).read_bytes();s=json.loads(raw);report={'created_at':time.time(),'source_window':[s['start'],s['end']],'source_sha256':hashlib.sha256(raw).hexdigest(),'method':'Hide entire 20/50/100m strips; assess final 20% time window only. Fixed methods, no fitting. Full visible context and hidden interval must lie in test partition.','groups':[],'examples':[]}
    for site in s['sites']:
        for direction in ['eastbound','westbound']:
            for width in [20,50,100]:
                cases=[]
                for track in site['tracks']:
                    if track['class_type'] not in VEHICLES or track['direction']!=direction:continue
                    m=masked(track,site['station_m'],width)
                    if m is None:continue
                    a,b,truth,begin,end=m
                    if begin<.8*(s['end']-s['start']):continue
                    a.update(class_type=track['class_type']);b.update(class_type=track['class_type']);cases.append((a,b,truth))
                result={'site':site['id'],'name':site['name'],'direction':direction,'width_m':width,'eligible':len(cases),'methods':{}}
                per_method={}
                for method in ['linear','hermite','monotone','queue']:
                    per_method[method]={}
                    errors=[];speeds=[];examples=[]
                    for case_id,(a,b,truth) in enumerate(cases):
                        pred=curve(a,b,method)
                        if pred is None:continue
                        p=np.array(pred);estimated=np.interp(truth[:,0],p[:,0],p[:,1]);mae=float(np.mean(abs(estimated-truth[:,1])));errors.append(mae);speeds.append(float(np.mean(abs(np.interp(truth[:,0],p[:,0],p[:,2])-truth[:,2]))))
                        per_method[method][case_id]={'mae_m':mae,'speed_mae_m_s':speeds[-1],'stop_go':bool(np.min(truth[:,2])<1 and np.max(truth[:,2])>4)}
                        if method=='monotone':examples.append({'mae_m':mae,'width_m':width,'site':site['name'],'direction':direction,'observed':truth.tolist(),'estimated':pred})
                    result['methods'][method]={'accepted':len(errors),'mae_m':float(np.mean(errors)) if errors else None,'p95_case_mae_m':float(np.quantile(errors,.95)) if errors else None,'speed_mae_m_s':float(np.mean(speeds)) if speeds else None}
                    if examples:
                        examples.sort(key=lambda e:e['mae_m']);report['examples'].extend([examples[len(examples)//2],examples[-1]])
                common=set.intersection(*(set(v) for v in per_method.values()))
                result['common_cases']={'count':len(common),'methods':{}}
                for method,metrics in per_method.items():
                    selected=[metrics[i] for i in sorted(common)];stops=[r for r in selected if r['stop_go']]
                    result['common_cases']['methods'][method]={'mae_m':float(np.mean([r['mae_m'] for r in selected])) if selected else None,'stop_go_count':len(stops),'stop_go_mae_m':float(np.mean([r['mae_m'] for r in stops])) if stops else None}
                # Remove one quarter of arrival fragments to simulate turns/missed detections.
                retained=[i for i in range(len(cases)) if i%4!=0]
                orphan_matches=associate([a for a,b,t in cases],[cases[i][1] for i in retained])
                orphan_correct=sum(m['left']==retained[m['right']] for m in orphan_matches)
                result['association_missing_arrivals']={'removed':len(cases)-len(retained),'matched':len(orphan_matches),'correct':orphan_correct,'false_matches':len(orphan_matches)-orphan_correct,'precision':orphan_correct/len(orphan_matches) if orphan_matches else None}
                matches=associate([a for a,b,t in cases],[b for a,b,t in cases]);correct=sum(m['left']==m['right'] for m in matches)
                result['association']={'matched':len(matches),'correct':correct,'precision':correct/len(matches) if matches else None,'recall':correct/len(cases) if cases else None}
                report['groups'].append(result)
    report['limitations']=['Known-endpoint trajectory errors and unknown-identity matching accuracy are different tasks.','Single-sensor masking cannot test cross-sensor clock offsets or alignment errors.','No lane labels, turning flow or verified signal states.','Errors across widths are correlated; no intermediate-road truth exists.','Curves are retrospective estimates using both visible ends, not causal forecasts.']
    output=Path(output);output.mkdir(parents=True,exist_ok=True);(output/'spatial-validation.json').write_text(json.dumps(report,indent=2))
    predictions={'start':s['start'],'end':s['end'],'generated_at':time.time(),**reconstruct(s)};(output/'spatial-paths.json').write_text(json.dumps(predictions,separators=(',',':')))
    return report
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--snapshot',required=True);p.add_argument('--output',required=True);a=p.parse_args();run(a.snapshot,a.output)
