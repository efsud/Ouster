"""Measured, locally tracked trajectories; never bridge the unobserved corridor."""
import argparse
from collections import Counter
from datetime import datetime
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.collections import LineCollection
from matplotlib.colors import Normalize
from .features import events
from dashboard.historical_ctm import VEHICLES

ZONE=ZoneInfo('America/Toronto')

def trajectories(records,rotation,bearing):
    angle=math.radians(rotation-bearing);c=math.cos(angle);s=math.sin(angle)
    active={};finished=[];kinds=Counter()
    def flush(key):
        points=active.pop(key,[])
        if len(points)<3:return
        a=np.asarray([p[:4] for p in points],dtype=float);travel=np.abs(np.diff(a[:,1])).sum();net=a[-1,1]-a[0,1]
        if a[-1,0]-a[0,0]<2 or abs(net)<3 or abs(net)<.7*travel:return
        finished.append({'direction':'eastbound' if net>0 else 'westbound','points':a[:,[0,1,3]]})
    for r in records:
        e=r['payload'];kinds.update(k for k in e if k!='timestamp');frame=e.get('frame')
        if frame is None:continue
        try:clock=datetime.fromisoformat(frame.get('timestamp') or e['timestamp'])
        except (KeyError,ValueError,TypeError):continue
        t=r['received_at']
        for o in frame.get('objects',[]):
            if str(o.get('classType')) not in VEHICLES or 'id' not in o:continue
            try:x=float(o['centerX']);y=float(o['centerY'])
            except (KeyError,TypeError,ValueError):continue
            along=c*x-s*y;across=s*x+c*y;key=(r['session'],str(o['id']))
            if not math.isfinite(along+across) or abs(along)>100 or abs(across)>12:
                flush(key);continue
            old=active.get(key)
            speed=0.
            if old:
                try:dt=(clock-old[-1][4]).total_seconds()
                except TypeError:dt=-1
                dr=t-old[-1][0]
                if not (0<dt<=3 and 0<dr<=3 and .5<=dt/dr<=2):flush(key);old=None
                else:
                    speed=math.hypot(along-old[-1][1],across-old[-1][2])/dt
                    if speed>60:flush(key);old=None;speed=0.
            active.setdefault(key,[]).append((t,along,across,speed,clock))
        if len(active)>1000:
            for key in list(active):
                if t-active[key][-1][0]>3:flush(key)
    for key in list(active):flush(key)
    return finished,dict(kinds)


def draw(tracks,direction,start,end,stations,path,title):
    fig,axes=plt.subplots(2,1,figsize=(12,8),sharex=True)
    fig.subplots_adjust(left=.085,right=.9,bottom=.105,top=.88,hspace=.28)
    colors=['#3467ad','#9b51aa'];norm=Normalize(0,20);total=0
    for site,items in enumerate(tracks):
        for tr in items:
            if tr['direction']!=direction:continue
            p=tr['points'];p=p[(p[:,0]>=start)&(p[:,0]<=end)]
            if len(p)<2:continue
            # Keep plot legible without altering stored trajectories.
            pick=np.r_[0,np.flatnonzero(np.diff(np.floor(p[:,0]*2)))+1,len(p)-1];p=p[np.unique(pick)]
            dates=mdates.date2num([datetime.fromtimestamp(v,ZONE) for v in p[:,0]])
            coords=np.column_stack([dates,p[:,1]+stations[site]])
            axes[0].plot(coords[:,0],coords[:,1],color=colors[site],lw=.55,alpha=.6)
            segments=np.stack([coords[:-1],coords[1:]],1)
            lc=LineCollection(segments,cmap='RdYlGn',norm=norm,linewidths=.8,alpha=.85);lc.set_array(p[1:,2]);axes[1].add_collection(lc);total+=1
    for ax in axes:
        ax.axhspan(100,stations[1]-100,color='#e5e8ec',alpha=.7)
        ax.text(.5,.5,'UNOBSERVED ROAD — no vehicle tracks inferred',transform=ax.transAxes,ha='center',color='#59616d',fontsize=9)
        for i,label in enumerate(['Weston','Signet / Arrow']):
            ax.axhline(stations[i],color=colors[i],linestyle='--',lw=1)
            ax.text(.005,stations[i]+10,label,transform=ax.get_yaxis_transform(),fontsize=9,color=colors[i])
        ax.set_ylim(-110,stations[1]+110);ax.set_xlim(mdates.date2num(datetime.fromtimestamp(start,ZONE)),mdates.date2num(datetime.fromtimestamp(end,ZONE)))
        ax.set_ylabel('Approximate station along Finch (m)');ax.grid(alpha=.15)
    axes[0].set_title(f'{direction.title()} direction-filtered vehicle tracks · colored by sensor ({total} fragments)',loc='left',fontsize=11)
    axes[1].set_title('Colored by displacement-derived speed · red = low speed, not a verified red signal',loc='left',fontsize=10)
    axes[1].xaxis.set_major_locator(mdates.MinuteLocator(interval=1 if end-start<=600 else 10,tz=ZONE))
    axes[1].xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S' if end-start<=600 else '%H:%M',tz=ZONE));axes[1].set_xlabel('Receipt time · America/Toronto · '+datetime.fromtimestamp(start,ZONE).strftime('%B %d, %Y'))
    fig.colorbar(plt.cm.ScalarMappable(norm=norm,cmap='RdYlGn'),cax=fig.add_axes([.92,.105,.018,.34]),label='Speed (m/s)',extend='max')
    fig.suptitle(title,fontsize=14,fontweight='bold')
    fig.text(.01,.012,'Measured local fragments; approximate geometry. No cross-sensor identity matching, signal states, queue or LOS claims.',fontsize=8,color='#555')
    fig.savefig(path,dpi=160);plt.close(fig)
    return total


def generate(directory):
    directory=Path(directory);config=json.loads((directory/'config.json').read_text());manifest=json.loads((directory/'manifest.json').read_text())
    if manifest['state'] not in ['captured','experiment_complete']:raise ValueError('Use a completed capture')
    out=directory/'figures';out.mkdir(exist_ok=True)
    site_config={s['id']:s for s in json.loads(Path('config/sites.json').read_text())['sites']}
    positions=[site_config[s]['reference_location'] for s in config['sites_west_to_east']]
    lat=math.radians(sum(p['lat'] for p in positions)/2)
    east=(positions[1]['lng']-positions[0]['lng'])*111320*math.cos(lat);north=(positions[1]['lat']-positions[0]['lat'])*111320
    spacing=math.hypot(east,north);tracks=[];metadata=[]
    for i,site in enumerate(config['sites_west_to_east']):
        t,kinds=trajectories(events(directory,site),config['rotation_deg'][i],config['road_bearing_east_deg']);tracks.append(t)
        metadata.append({'site':site,'event_types':kinds,'accepted_fragments':len(t)})
    entries=[]
    for direction in ['eastbound','westbound']:
        name=direction+'-hour.png';count=draw(tracks,direction,manifest['start'],manifest['end'],[0,spacing],out/name,'Weston ↔ Signet / Arrow · recorded hour')
        entries.append({'file':name,'direction':direction,'label':'Full recorded hour','fragments':count})
        start=math.floor(manifest['start']/300)*300
        while start+60<manifest['end']:
            end=min(start+300,manifest['end']);name=f'{direction}-{int(start)}.png'
            label=f'{datetime.fromtimestamp(start,ZONE):%H:%M}–{datetime.fromtimestamp(end,ZONE):%H:%M}'
            count=draw(tracks,direction,start,end,[0,spacing],out/name,'Weston ↔ Signet / Arrow · '+label+' Toronto')
            entries.append({'file':name,'direction':direction,'label':label,'fragments':count});start+=300
    report={'source':'measured-trajectories','station_spacing_m':spacing,'spacing_basis':'straight-line separation of user-provided approximate sensor coordinates, not surveyed road distance','sites':metadata,'figures':entries,'limitations':['Direction filtering is provisional; straight-through movements are not independently verified.','Receipt clocks are used; sensor clock offsets remain unverified.','Separate sensor track IDs are never joined.','No measured observations exist in the shaded road segment.','These are not DeepCTM forecasts.']}
    (out/'index.json').write_text(json.dumps(report,indent=2));print(json.dumps({'figures':len(entries),'sites':metadata,'spacing_m':spacing}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--capture',required=True);a=p.parse_args();generate(a.capture)
