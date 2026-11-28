"""Read-only road-alignment diagnostic on fresh recorded moving segments.

Uses cached map geometry, never changes calibration. Splits by time before angle
selection; an improved road-axis score is not proof of correct vehicle identity.
"""
import argparse,json,math,sqlite3,time
from datetime import datetime
from pathlib import Path
import numpy as np
from scripts.audit_map_rotations import roads,score
from .corridor_campaign import atomic

def segments(rows):
    previous={};result=[]
    for session,receipt,payload in rows:
        event=json.loads(payload);frame=event.get('frame',{})
        try:stamp=datetime.fromisoformat(frame.get('timestamp') or event['timestamp']).timestamp()
        except (ValueError,KeyError,TypeError):continue
        for obj in frame.get('objects',[]):
            if str(obj.get('classType')) not in {'1','2','3','4','5','6','7','8','9','15'}:continue
            try:p=np.array([float(obj['centerX']),float(obj['centerY'])]);key=(session,str(obj['id']))
            except (ValueError,TypeError,KeyError):continue
            if not np.isfinite(p).all():continue
            old=previous.get(key)
            if old is None:previous[key]=(stamp,receipt,p);continue
            dt=stamp-old[0];dr=receipt-old[1]
            if dt<1:continue
            previous[key]=(stamp,receipt,p);delta=p-old[2];length=np.linalg.norm(delta);mid=(p+old[2])/2
            if 1<=dt<=2 and 0<dr<=3 and .5<dt/dr<2 and 4<length/dt<30 and 25<np.linalg.norm(mid)<150:
                result.append([receipt,*mid,*(delta/length)])
    return np.asarray(result)

def plot_comparison(samples,a,b,names,current,candidate,path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axs=plt.subplots(1,2,figsize=(12,6),sharex=True,sharey=True)
    for ax,(angle,mirror,label) in zip(axs,(current,candidate)):
        p=samples.copy()
        if mirror:p[:,[2,4]]*=-1
        theta=math.radians(angle);rotation=np.array([[math.cos(theta),-math.sin(theta)],[math.sin(theta),math.cos(theta)]])
        pos=p[:,1:3]@rotation.T;vel=p[:,3:5]@rotation.T
        for x,y,name in zip(a,b,names):ax.plot([x[0],y[0]],[x[1],y[1]],color='gray',alpha=.7,linewidth=3 if 'Finch' in name else 1)
        ax.quiver(pos[:,0],pos[:,1],vel[:,0],vel[:,1],np.arctan2(vel[:,1],vel[:,0]),cmap='twilight',scale=25,width=.002)
        ax.scatter([0],[0],marker='x',color='black');ax.set(xlim=(-170,170),ylim=(-170,170),aspect='equal',xlabel='East (m)',title=label);ax.grid(alpha=.2)
    axs[0].set_ylabel('North (m)');fig.suptitle('Provisional origin; cached OSM centerlines; arrows are recorded moving segments')
    fig.tight_layout(rect=(0,0,1,.90));fig.savefig(path,dpi=150,bbox_inches='tight',pad_inches=.2);plt.close(fig)

def run(region,output,site_id=None,plot=False):
    root=Path(__file__).resolve().parents[1];name='Toronto' if region=='finch' else 'Florida'
    entries=[s for s in json.loads((root/'config/sites.json').read_text())['sites'] if s['region']==name]
    if site_id:entries=[s for s in entries if s['id']==site_id]
    from .buffer_snapshot import copy_buffer
    db=copy_buffer(root/f'data/{region}-rolling/buffer.sqlite3')
    end=db.execute('select max(received) from frames').fetchone()[0];start=end-1200;cut=end-600
    ways=json.loads((root/f'data/alignment/{name}-roads.json').read_text())['elements'];result=[]
    for site in entries:
        p=segments(db.execute('select session,received,payload from frames where site=? and received>=? order by received',(site['id'],start)))
        row={'site':site['id'],'name':site['name'],'segments':len(p),'rotation_deg':site.get('preview_rotation_deg',220),'mirror_y':site.get('preview_mirror_y',False)}
        if len(p)<100:row['state']='insufficient_segments';result.append(row);continue
        train=p[p[:,0]<cut];test=p[p[:,0]>=cut]
        if min(len(train),len(test))<50:row['state']='insufficient_time_split';result.append(row);continue
        train=train[np.linspace(0,len(train)-1,min(600,len(train))).astype(int)]
        test=test[np.linspace(0,len(test)-1,min(600,len(test))).astype(int)]
        if row['mirror_y']:train[:,[2,4]]*=-1;test[:,[2,4]]*=-1
        a,b,names,oneway=roads(ways,site['reference_location'])
        if not len(a):row['state']='no_cached_roads';result.append(row);continue
        costs=[score(train,a,b,d,oneway=oneway) for d in range(360)];best=int(np.argmin(costs))
        reflected=train.copy();reflected[:,[2,4]]*=-1
        reflected_costs=[score(reflected,a,b,d,oneway=oneway) for d in range(360)];reflected_best=int(np.argmin(reflected_costs))
        reflected_test=test.copy();reflected_test[:,[2,4]]*=-1
        row.update(state='diagnostic_only',candidate_rotation_deg=best,oneway_segments=int(np.count_nonzero(oneway)),
            current=score(test,a,b,row['rotation_deg'],True,oneway),candidate=score(test,a,b,best,True,oneway),
            opposite=score(test,a,b,(row['rotation_deg']+180)%360,True,oneway),
            reflected_rotation_deg=reflected_best,reflected_mirror_y=not row['mirror_y'],
            reflected=score(reflected_test,a,b,reflected_best,True,oneway),
            selected_reflection_from_training=min(reflected_costs)<min(costs))
        if plot:
            raw_test=test.copy()
            if row['mirror_y']:raw_test[:,[2,4]]*=-1
            reflected_selected=row['selected_reflection_from_training']
            plot_comparison(raw_test,a,b,names,(row['rotation_deg'],row['mirror_y'],'Current '+site['name']),
                (reflected_best if reflected_selected else best,not row['mirror_y'] if reflected_selected else row['mirror_y'],'Unpublished candidate'),Path(output).with_name(site['id']+'-comparison.png'))
        result.append(row);print(site['name'],row['rotation_deg'],best,round(row['current']['score'],2),round(row['candidate']['score'],2),flush=True)
    db.close();report={'window':[start,end],'split':cut,'sites':result,'created_at':time.time(),
        'limitations':['Cached OSM centerlines are not surveyed lane geometry.','Turns and approximate sensor origins affect scores.','No calibration edits or identity claims.','Receipt times used for split; sensor timestamps only check local segment speed.']}
    atomic(Path(output),report);return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--region',choices=['finch','florida'],required=True);p.add_argument('--output',required=True);p.add_argument('--site');p.add_argument('--plot',action='store_true');a=p.parse_args();run(a.region,a.output,a.site,a.plot)
