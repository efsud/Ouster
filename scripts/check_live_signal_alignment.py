import sys,json,sqlite3,time,math
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from dashboard.server import sites
from scripts.audit_map_rotations import roads,score
entries=sites();dbs={r:sqlite3.connect(f'file:{ROOT}/data/{n}-live.sqlite3?mode=ro',uri=True) for r,n in [('Toronto','finch'),('Florida','florida')]}
prev={};samples={s['id']:[] for s in entries};keys={};start=time.time()
while time.time()-start<65:
 for s in entries:
  row=dbs[s['region']].execute('select event_key,session,received_at,payload from preview_frames where site=?',(s['id'],)).fetchone()
  if not row or keys.get(s['id'])==row[0] or time.time()-row[2]>3:continue
  keys[s['id']]=row[0];event=json.loads(row[3])
  for o in event.get('frame',{}).get('objects',[]):
   if str(o.get('classType')) not in {'1','2','3','4','5','6','7','8','9','15'}:continue
   x,y=float(o.get('centerX',0)),float(o.get('centerY',0));key=(s['id'],row[1],o.get('id'));old=prev.get(key);prev[key]=(row[2],x,y)
   if old:
    dt=row[2]-old[0];dx=x-old[1];dy=y-old[2];length=math.hypot(dx,dy)
    if .5<dt<2 and 3<length/dt<25 and 30<math.hypot(x,y)<150:
     samples[s['id']].append([row[2]-start,(x+old[1])/2,(y+old[2])/2,dx/length,dy/length])
 time.sleep(1)
result=[]
for s in entries:
 p=np.asarray(samples[s['id']]);r={'site':s['id'],'name':s['name'],'segments':len(p),'rotation_deg':s.get('preview_rotation_deg',220),'mirror_y':s.get('preview_mirror_y',False)}
 if len(p)>=30:
  if s.get('preview_mirror_y'):p[:,[2,4]]*=-1
  if len(p)>400:p=p[np.linspace(0,len(p)-1,400).astype(int)]
  a,b,_,oneway=roads(json.load(open(ROOT/'data/alignment'/f"{s['region']}-roads.json"))['elements'],s['reference_location'])
  r['current']=score(p,a,b,r['rotation_deg'],True,oneway)
  r['opposite']=score(p,a,b,(r['rotation_deg']+180)%360,True,oneway)
 else:r['state']='insufficient fresh moving segments'
 result.append(r)
path=ROOT/'data/alignment/live-signal-alignment-review.json';path.write_text(json.dumps({'collected_at':time.time(),'duration_s':65,'note':'Provisional cached OSM comparison; road-axis fit cannot prove phase mapping. No calibration changes applied.','sites':result},indent=2))
for r in result:print(r['name'],r['segments'],'current',round(r.get('current',{}).get('score',0),1),'opposite',round(r.get('opposite',{}).get('score',0),1))
