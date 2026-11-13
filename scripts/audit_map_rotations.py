"""Compare raw moving-vehicle segments with OSM road geometry; no automatic calibration."""
import sys,json,math,gzip
from pathlib import Path
from datetime import datetime
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dashboard.historical_ctm import VEHICLES

def samples(directory,site):
    prev={};rows=[];first=None
    for path in sorted(Path(directory).glob(site+'-*.jsonl.gz')):
        with gzip.open(path,'rt') as stream:
            for line in stream:
                r=json.loads(line);e=r['payload'];frame=e.get('frame')
                if frame is None:continue
                receipt=r['received_at'];first=receipt if first is None else first
                if receipt-first>610:return np.asarray(rows)
                try:t=datetime.fromisoformat(frame.get('timestamp') or e['timestamp']).timestamp()
                except (ValueError,KeyError,TypeError):continue
                for o in frame.get('objects',[]):
                    if str(o.get('classType')) not in VEHICLES:continue
                    try:p=np.array([float(o['centerX']),float(o['centerY'])]);key=(r['session'],o['id'])
                    except (KeyError,ValueError,TypeError):continue
                    if not np.isfinite(p).all() or np.linalg.norm(p)>180:continue
                    old=prev.get(key)
                    if old is None:prev[key]=(t,receipt,p);continue
                    dt=t-old[0];dr=receipt-old[1]
                    if dt<1:continue
                    prev[key]=(t,receipt,p)
                    delta=p-old[2];distance=np.linalg.norm(delta)
                    if 0<dt<=2 and 0<dr<=2 and .5<dt/dr<2 and 4<distance/dt<30 and receipt-first>10:
                        mid=(p+old[2])/2
                        if np.linalg.norm(mid)>15:rows.append([receipt-first,*mid,*(delta/distance)])
    return np.asarray(rows)

def roads(elements,origin):
    scale=np.array([111320*math.cos(math.radians(origin['lat'])),111320]);a=[];b=[];names=[];oneway=[]
    for way in elements:
        tags=way.get('tags',{})
        if tags.get('highway') in ['service','track','living_street']:continue
        g=way.get('geometry',[])
        for u,v in zip(g,g[1:]):
            x=(np.array([u['lon'],u['lat']])-np.array([origin['lng'],origin['lat']]))*scale
            y=(np.array([v['lon'],v['lat']])-np.array([origin['lng'],origin['lat']]))*scale
            if min(np.linalg.norm(x),np.linalg.norm(y))>300 or np.linalg.norm(y-x)<1:continue
            a.append(x);b.append(y);names.append(tags.get('name','unnamed'));oneway.append(-1 if tags.get('oneway')=='-1' else 1 if tags.get('oneway') in ['yes','1','true'] else 0)
    return np.asarray(a),np.asarray(b),names,np.asarray(oneway)

def score(samples,a,b,angle,detail=False,oneway=None):
    theta=math.radians(angle);rot=np.array([[math.cos(theta),-math.sin(theta)],[math.sin(theta),math.cos(theta)]])
    pos=samples[:,1:3]@rot.T;vel=samples[:,3:5]@rot.T;segment=b-a;length=np.linalg.norm(segment,axis=1);unit=segment/length[:,None]
    fraction=np.clip(((pos[:,None]-a)*segment).sum(axis=2)/(length**2),0,1)
    distance=np.linalg.norm(pos[:,None]-a-fraction[:,:,None]*segment,axis=2)
    dot=vel@unit.T
    alignment=np.abs(dot) if oneway is None else np.where(oneway[None,:]==0,np.abs(dot),dot*oneway[None,:])
    angular=np.degrees(np.arccos(np.clip(alignment,-1,1)))
    cost=distance+angular*.6;best=cost.argmin(axis=1);idx=np.arange(len(pos))
    # A trimmed mean prevents a few turns dominating the axis estimate.
    values=np.sort(cost[idx,best]);result=float(values[:max(1,int(len(values)*.8))].mean())
    if detail:return {'score':result,'median_road_distance_m':float(np.median(distance[idx,best])),'median_axis_error_deg':float(np.median(angular[idx,best]))}
    return result

def main():
    output=ROOT/'data/alignment';output.mkdir(exist_ok=True);result=[]
    sites=json.loads((ROOT/'config/sites.json').read_text())['sites']
    for site in sites:
        region=site['region'];directory=ROOT/('data/sr436/20261113T115900Z-89fb0f' if region=='Florida' else 'data/deepctm/20261106T164305Z')
        cache=output/(site['id']+'-samples.npy')
        if cache.exists():p=np.load(cache)
        else:p=samples(directory,site['id']);np.save(cache,p)
        row={'site':site['id'],'name':site['name'],'region':region,'old_rotation_deg':site.get('preview_rotation_deg',220),'samples':len(p),'source_capture':directory.name}
        if len(p)<100:row['state']='insufficient_tracks';result.append(row);print(row,flush=True);continue
        train=p[p[:,0]<310];test=p[p[:,0]>=310]
        if len(test)<50:row['state']='insufficient_validation';result.append(row);continue
        train=train[np.linspace(0,len(train)-1,min(600,len(train))).astype(int)];test=test[np.linspace(0,len(test)-1,min(600,len(test))).astype(int)]
        a,b,names,oneway=roads(json.loads((output/(region+'-roads.json')).read_text())['elements'],site['reference_location'])
        if len(a)==0:row['state']='no_roads';result.append(row);continue
        normal_scores=[score(train,a,b,d,oneway=oneway) for d in range(360)]
        mirrored_train=train.copy();mirrored_train[:,[2,4]]*=-1
        mirror_scores=[score(mirrored_train,a,b,d,oneway=oneway) for d in range(360)]
        mirrored=min(mirror_scores)<min(normal_scores)
        scores=mirror_scores if mirrored else normal_scores;best=int(np.argmin(scores))
        validation=test.copy()
        if mirrored:validation[:,[2,4]]*=-1
        row.update(candidate_mirror_y=mirrored,mirror_improvement=(min(normal_scores)-min(mirror_scores))/max(min(normal_scores),1),oneway_segments=int(np.count_nonzero(oneway)))
        alternatives=[d for d in range(360) if abs((d-best+180)%360-180)>=25];second=min(alternatives,key=lambda d:scores[d])
        row.update(state='review_required',candidate_rotation_deg=best,alternative_rotation_deg=second,relative_margin=(scores[second]-scores[best])/max(scores[best],1),validation_before=score(test,a,b,row['old_rotation_deg'],True,oneway),validation_after=score(validation,a,b,best,True,oneway),road_names=sorted(set(names)))
        result.append(row);print(site['name'],row['old_rotation_deg'],'->',best,'mirror',mirrored,'alternative',second,'margin',round(row['relative_margin'],2),'validation',round(row['validation_before']['score'],1),round(row['validation_after']['score'],1),flush=True)
        (output/'rotation-audit.json').write_text(json.dumps(result,indent=2))
    (output/'rotation-audit.json').write_text(json.dumps(result,indent=2))
if __name__=='__main__':main()
