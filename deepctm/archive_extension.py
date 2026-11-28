"""Independent-period evaluation: learned shape prior and calibrated association.

Train: AM first 30 min. Select: AM after 31 min. Test: PM first hour.
Known IDs are scoring labels only in blind-band association. No cross-site truth.
"""
import argparse,hashlib,json,time
from pathlib import Path
import numpy as np
from .reconstruction_study import masked_case,metrics,summarize
from .trajectory_reconstruction import baseline,refine
from .integrated_reconstruction import reconstruct
from .validate_spatial import masked
from .spatial_bridges import associate,curve,pair_cost

GAPS=(10,30,60,90)
def cases(snapshot,part,limit=3,classes=('2',)):
    groups={}
    for site in snapshot['sites']:
        for tr in site['tracks']:
            if tr['class_type'] not in classes:continue
            p=tr['points']
            if part=='train' and p[-1][0]>1800:continue
            if part=='validation' and p[0][0]<1860:continue
            rank=hashlib.sha256(json.dumps([site['id'],tr['source_key'],p[0][0]]).encode()).hexdigest()
            for gap in GAPS:
                m=masked_case(tr,gap)
                if m:groups.setdefault((site['id'],tr['direction'],gap),[]).append((rank,site,tr,gap,m))
    return [v for _,rows in sorted(groups.items()) for v in sorted(rows,key=lambda x:x[0])[:limit]]

def features(a,b,center):
    dt=b['t']-a['t'];dx=b['x']-a['x'];avg=dx/dt
    return np.array([a['v']/max(avg,1),b['v']/max(avg,1),np.log(dt),avg/10,(a['x']-center)/50])

def fit(rows):
    X=[];Y=[]
    for _,site,tr,gap,(a,b,truth) in rows:
        if b['x']-a['x']<5:continue
        center=site['station_m']*(1 if tr['direction']=='eastbound' else -1)
        t=np.linspace(a['t'],b['t'],41);p=baseline(a,b)
        y=np.interp(t,np.r_[a['t'],truth[:,0],b['t']],np.r_[a['x'],truth[:,1],b['x']])
        residual=(y-np.interp(t,p[:,0],p[:,1]))/max(10,b['x']-a['x'])
        residual[[0,-1]]=0;X.append(features(a,b,center));Y.append(residual)
    X=np.array(X);return X,np.array(Y),np.maximum(np.std(X,axis=0),.1)

def estimate(site,tr,a,b,model,params,weight):
    ref=baseline(a,b);X,Y,scale=model
    center=site['station_m']*(1 if tr['direction']=='eastbound' else -1)
    distances=np.sqrt(np.mean(((X-features(a,b,center))/scale)**2,axis=1));ids=np.argsort(distances)[:5]
    supported=len(ids)>=5 and distances[ids[-1]]<=2 and b['x']-a['x']>=5
    if supported and weight>0:
        residual=np.average(Y[ids],axis=0,weights=1/np.maximum(distances[ids],.1))
        ref[:,1]+=weight*max(10,b['x']-a['x'])*np.interp(ref[:,0],np.linspace(a['t'],b['t'],41),residual)
        ref[:,2]=np.gradient(ref[:,1],ref[:,0]);ref[0,2]=a['v'];ref[-1,2]=b['v']
    r=refine(a,b,ref,**params,smoothness=.01,position_tolerance=0,speed_tolerance=0)
    return r,supported

def summary(scores,rows):
    return {'accepted':len(scores),'eligible':len(rows),'metrics':summarize(list(scores.values()))}

def association_groups(snapshot,part):
    groups={}
    for site in snapshot['sites']:
        for tr in site['tracks']:
            if tr['class_type']!='2':continue
            p=tr['points']
            if part=='train' and p[-1][0]>1800 or part=='validation' and p[0][0]<1860:continue
            rank=hashlib.sha256(json.dumps([site['id'],tr['source_key'],p[0][0]]).encode()).hexdigest()
            width=(20,50,100)[int(rank[:8],16)%3];m=masked(tr,site['station_m'],width)
            if m:
                a,b,*_=m;groups.setdefault((site['id'],tr['direction'],width),[]).append((rank,dict(a,class_type='2'),dict(b,class_type='2')))
    return groups

def calibrated(left,right,ratio,margin):
    edges={};aa={};bb={}
    for i,a in enumerate(left):
        for j,b in enumerate(right):
            base=pair_cost(a,b)
            if base is None:continue
            expected=ratio*abs(b['x']-a['x'])/((abs(a['v'])+abs(b['v']))/2)
            cost=abs(b['t']-a['t']-expected)/max(2,.35*expected)+abs(abs(a['v'])-abs(b['v']))/15
            if cost>1.5 or curve(a,b) is None:continue
            edges[i,j]=cost;aa.setdefault(i,[]).append((cost,j));bb.setdefault(j,[]).append((cost,i))
    for options in (*aa.values(),*bb.values()):options.sort()
    pairs=[]
    for i,options in aa.items():
        cost,j=options[0];rev=bb[j]
        if rev[0][1]!=i:continue
        if min(options[1][0]-cost if len(options)>1 else 99,rev[1][0]-cost if len(rev)>1 else 99)<margin:continue
        pairs.append({'left':i,'right':j,'cost':cost,'margin':min(options[1][0]-cost if len(options)>1 else 99,rev[1][0]-cost if len(rev)>1 else 99),'points':curve(left[i],right[j])})
    return pairs

def association_scores(groups,methods,ratio):
    results={}
    for scenario in ('complete','missing_both'):
        results[scenario]={}
        for method in methods:
            counts=dict(eligible=0,matched=0,correct=0,false=0)
            for _,rows in sorted(groups.items()):
                rows=sorted(rows);ai=[i for i,r in enumerate(rows) if scenario=='complete' or int(r[0][8:16],16)%5];bi=[i for i,r in enumerate(rows) if scenario=='complete' or int(r[0][16:24],16)%4][::-1]
                left=[rows[i][1] for i in ai];right=[rows[i][2] for i in bi]
                matches=associate(left,right,method='feasible') if method=='current' else calibrated(left,right,ratio,float(method.split('_')[1]))
                correct=sum(ai[m['left']]==bi[m['right']] for m in matches)
                counts['eligible']+=len(set(ai)&set(bi));counts['matched']+=len(matches);counts['correct']+=correct;counts['false']+=len(matches)-correct
            counts['precision']=counts['correct']/counts['matched'] if counts['matched'] else None;counts['recall']=counts['correct']/counts['eligible'] if counts['eligible'] else None
            results[scenario][method]=counts
    return results

def run(am,pm,study,output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    morning=json.loads(Path(am).read_text());params=json.loads(Path(study).read_text())['calibration']['parameters']
    train=cases(morning,'train',10000);model=fit(train);train_ids={(r[1]['id'],*r[2]['source_key'][:2]) for r in train};val=[r for r in cases(morning,'validation') if (r[1]['id'],*r[2]['source_key'][:2]) not in train_ids];report={'created_at':time.time(),'parameters':params,'training_masks':len(train),'training_templates':len(model[0]),'gap_seconds':GAPS,'source_hashes':{str(p):hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in (am,pm)},'split':'AM 07:00-07:30 train; AM 07:31-08:00 select; PM 16:00-17:00 test, America/New_York; entire fragment must fit partition','results':{}}
    def save():
        temp=output/'report.tmp';temp.write_text(json.dumps(report,indent=2,allow_nan=False));temp.replace(output/'report.json')
    def evaluate(rows,methods,label):
        scores={m:{} for m in methods};support={m:0 for m in methods}
        for i,(_,site,tr,gap,(a,b,truth)) in enumerate(rows):
            for method in methods:
                if method=='integrated':r=reconstruct(site,tr,a,b,params)
                else:r,used=estimate(site,tr,a,b,model,params,0 if method=='current' else float(method.split('_')[1]));support[method]+=int(used and method!='current')
                if r['state']=='candidate':scores[method][i]=metrics(r['points'],truth,params)
            if i%20==0:print(label,i,len(rows),flush=True)
        common=set.intersection(*(set(s) for s in scores.values()));out={m:dict(summary(s,rows),common=summarize([s[i] for i in common]),prior_used=support[m],by_gap={str(g):summarize([s[i] for i in common if rows[i][3]==g]) for g in GAPS}) for m,s in scores.items()}
        return scores,out
    scores,report['results']['validation']=evaluate(val,['current','learned_0.25','learned_0.5'],'validation')
    # Choose only if coverage does not decline and common-case position improves.
    winner=min(report['results']['validation'],key=lambda m:report['results']['validation'][m]['common'].get('mae_m',float('inf')) if len(scores[m])>=len(scores['current']) else float('inf'))
    report['selected_shape']=winner
    train_groups=association_groups(morning,'train');ratios=[]
    for rows in train_groups.values():
        for _,a,b in rows:
            if pair_cost(a,b) is not None:ratios.append((b['t']-a['t'])*(abs(a['v'])+abs(b['v']))/2/abs(b['x']-a['x']))
    ratio=float(np.clip(np.median(ratios),.75,1.5));report['association_calibration']={'time_ratio':ratio,'training_pairs':len(ratios)}
    report['association_validation']=association_scores(association_groups(morning,'validation'),['current','calibrated_0.1','calibrated_0.25','calibrated_0.5'],ratio)
    eligible=[m for m in report['association_validation']['complete'] if all((s[m]['precision'] or 0)>=.98 and s[m]['false']<=s['current']['false'] for s in report['association_validation'].values())]
    choice=max(eligible,key=lambda m:min(s[m]['recall'] or 0 for s in report['association_validation'].values())) if eligible else 'current'
    report['selected_association']=choice;report['state']='selection_frozen';save()
    afternoon=json.loads(Path(pm).read_text());test=cases(afternoon,'test');methods=list(dict.fromkeys(['current',winner,'integrated']))
    scores,report['results']['test']=evaluate(test,methods,'test')
    report['association_test']=association_scores(association_groups(afternoon,'test'),list(dict.fromkeys(['current',choice])),ratio)
    report['paired']={}
    for method in methods[1:]:
        ids=sorted(set(scores[method])&set(scores['current']));gain=np.array([scores['current'][i]['mae_m']-scores[method][i]['mae_m'] for i in ids]);rng=np.random.default_rng(172)
        report['paired'][method]={'n':len(ids),'improvement_m':float(gain.mean()),'mask_bootstrap95_m':np.quantile(rng.choice(gain,(2000,len(gain)),replace=True).mean(axis=1),[.025,.975]).tolist()}
    report['limitations']=['Spatial masks validate known same-sensor identities, not real intersensor identity or missing-road truth.','Long gaps reuse tracks; intervals are exploratory mask bootstrap, not independent days.','Two disjoint hours on one archival day; calibration and receipt clocks provisional.','Archived signal state not replayed: integrated comparator uses CTM and available estimated leaders, not signal evidence.','Only continuous car tracks support truth; stopped tracks with no net displacement excluded by original extractor.','Retrospective endpoint-conditioned estimates, not causal forecasts.','No live model changed from this experiment.'];report['state']='complete';save();print('DONE',output,flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--am',required=True);p.add_argument('--pm',required=True);p.add_argument('--study',required=True);p.add_argument('--output',required=True);a=p.parse_args();run(a.am,a.pm,a.study,a.output)
