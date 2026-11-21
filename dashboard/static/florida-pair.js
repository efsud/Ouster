'use strict';
const el=id=>document.getElementById(id),clock=t=>new Date(t*1000).toLocaleTimeString('en-CA',{timeZone:'America/New_York',hour12:false});
let data=null,hits=[];
function choose(){const d=data.directions[el('direction').value];el('origin').replaceChildren();for(const [i,run] of (d.runs||[]).entries()){const o=document.createElement('option');o.value=i;o.textContent=clock(run.origin);el('origin').append(o);}render();}
function render(){
 const d=data.directions[el('direction').value],model=el('model').value,run=d.runs?.[Number(el('origin').value)];
 el('metrics').replaceChildren();if(!run){el('status').textContent='Insufficient data for this direction.';return;}
 const length=data.config.origin_distance_m,duration=data.config.horizon_steps*data.config.interval_s;
 el('detail').textContent=`Forecast ${clock(run.origin)}–${clock(run.origin+duration)} · ${length.toFixed(1)} m between configured origins · ${model}. Select a single forecast; paths never stitch together different forecast runs.`;
 const canvas=el('chart'),w=canvas.clientWidth,h=560,dpr=devicePixelRatio||1;canvas.width=w*dpr;canvas.height=h*dpr;const c=canvas.getContext('2d');c.scale(dpr,dpr);hits=[];
 const x=t=>80+t/duration*(w-100),y=s=>h-60-(s+40)/(length+80)*(h-90);
 c.font='12px sans-serif';c.strokeStyle='#dce3e8';c.fillStyle='#34434e';
 for(let i=0;i<=4;i++){const t=duration*i/4;c.beginPath();c.moveTo(x(t),20);c.lineTo(x(t),h-60);c.stroke();c.fillText(clock(run.origin+t),Math.min(w-65,x(t)-25),h-30);}
 for(const [s,label] of [[0,'Palm Springs Dr'],[length,'Boston Ave']]){c.fillStyle='#edf3f6';c.fillRect(80,y(s+30),w-100,y(s-30)-y(s+30));c.fillStyle='#34434e';c.fillText(label,85,y(s)-8);c.fillText(s.toFixed(0)+' m',5,y(s));}
 for(const path of run.models[model]){let offset=0;for(let i=1;i<path.points.length;i++){const a=path.points[i-1],b=path.points[i];c.strokeStyle=`hsl(${Math.max(0,Math.min(120,b[2]*6))},75%,40%)`;c.lineWidth=2;c.setLineDash([7,5]);c.lineDashOffset=-offset;c.beginPath();c.moveTo(x(a[0]),y(a[1]));c.lineTo(x(b[0]),y(b[1]));c.stroke();offset+=Math.hypot(x(b[0])-x(a[0]),y(b[1])-y(a[1]));hits.push({x:x(b[0]),y:y(b[1]),time:run.origin+b[0],station:b[1],speed:b[2]});}}
 c.setLineDash([]);
 for(const name of ['DeepCTM','Persistence','Pure CTM'])for(const [lead,row] of Object.entries(d.metrics[name])){const tr=document.createElement('tr');for(const text of [lead+' s',name,...['flow_veh_h','density_veh_km','speed_kmh'].map(k=>row[k].rmse===null?'Unavailable':row[k].rmse.toFixed(2))]){const td=document.createElement('td');td.textContent=text;tr.append(td);}el('metrics').append(tr);}
 el('quality').textContent=`Train / validation / test sequences: ${d.counts.train} / ${d.counts.validation} / ${d.counts.test}. Selected epoch ${d.best_epoch}. DeepCTM mean mass discrepancy ${d.mean_mass_residual_vehicles.toFixed(4)} vehicles per cell-step; neural updates are not exactly conservative.`;
}
el('direction').onchange=choose;el('origin').onchange=render;el('model').onchange=render;window.addEventListener('resize',()=>{if(data)render();});
el('chart').onmousemove=e=>{const r=el('chart').getBoundingClientRect();let nearest=null,best=100;for(const p of hits){const d=(e.clientX-r.left-p.x)**2+(e.clientY-r.top-p.y)**2;if(d<best){best=d;nearest=p;}}el('hover').textContent=nearest?`${clock(nearest.time)} · ${nearest.station.toFixed(1)} m · ${nearest.speed.toFixed(1)} m/s (predicted)`:'Hover over a path for predicted time, station and speed.';};
fetch('/api/florida-pair').then(r=>{if(!r.ok)throw Error('Model result is not ready.');return r.json();}).then(d=>{data=d;el('status').textContent='Experimental model results · 90-minute source window · endpoint evaluation only.';for(const text of d.config.assumptions){const li=document.createElement('li');li.textContent=text;el('limits').append(li);}choose();}).catch(e=>{el('status').textContent=e.message;});
