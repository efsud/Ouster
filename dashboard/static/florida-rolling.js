'use strict';
const el=id=>document.getElementById(id),vehicle=new Set(['1','2','3','4','5','6','7','8','9','15']);
const corridor=document.body.dataset.corridor||'florida',regionName=corridor==='finch'?'Toronto':'Florida';
let data=null,view=null,points=[],version=0;
const clock=t=>new Date(t*1000).toLocaleTimeString('en-CA',{timeZone:corridor==='finch'?'America/Toronto':'America/New_York',hour12:false});
function color(v){const t=Math.max(0,Math.min(1,v/20));return `hsl(${t*120},75%,40%)`;}
function draw(){
 if(!data)return;const panRange=data.end-data.start-(view[1]-view[0]);el('time').value=panRange>0?1000*(view[0]-data.start)/panRange:0;const selected=new Set([...el('sites').querySelectorAll('input:checked')].map(n=>n.value)),sites=data.sites.filter(s=>selected.has(s.id));
 renderMovements(sites);
 const canvas=el('plot'),w=canvas.clientWidth,h=650,dpr=window.devicePixelRatio||1;canvas.width=w*dpr;canvas.height=h*dpr;const c=canvas.getContext('2d');c.scale(dpr,dpr);c.clearRect(0,0,w,h);points=[];
 if(!sites.length){c.fillText('Select an intersection.',30,40);return;}
 const lo=Math.min(...sites.map(s=>s.station_m))-130,hi=Math.max(...sites.map(s=>s.station_m))+130;
 const x=t=>90+(t-view[0])/(view[1]-view[0])*(w-110),y=s=>h-50-(s-lo)/(hi-lo)*(h-80);
 c.font='12px sans-serif';c.fillStyle='#52636d';c.strokeStyle='#dbe3e8';
 for(let i=0;i<=6;i++){const t=view[0]+i*(view[1]-view[0])/6;c.beginPath();c.moveTo(x(t),20);c.lineTo(x(t),h-50);c.stroke();c.fillText(clock(t),Math.min(w-65,x(t)-25),h-25);}
 for(const s of sites){c.fillStyle='#263b46';c.fillText(s.name,95,y(s.station_m)-8);c.fillText(Math.round(s.station_m)+' m',4,y(s.station_m));c.strokeStyle='#c3cdd3';c.beginPath();c.moveTo(90,y(s.station_m));c.lineTo(w-20,y(s.station_m));c.stroke();}
 c.save();c.beginPath();c.rect(90,20,w-110,h-70);c.clip();let count=0;
 for(const site of sites)for(const tr of site.tracks){
  const filter=el('objects').value,code=tr.class_type;if(tr.direction!==el('direction').value)continue;
  if(filter==='vehicles'&&!vehicle.has(code)||filter==='pedestrians'&&!['0','10','11','14','16'].includes(code)||filter==='cyclists'&&!['12','13','17'].includes(code))continue;
  if(tr.method)continue;
  let seen=false;
  for(let i=1;i<tr.points.length;i++){
   const a=tr.points[i-1],b=tr.points[i],ta=data.start+a[0],tb=data.start+b[0],dt=b[0]-a[0];
   if(dt<=0||dt>1.5||tb<view[0]||ta>view[1])continue;
   seen=true;c.strokeStyle=color(b[2]);c.lineWidth=1;c.setLineDash([]);
   c.beginPath();c.moveTo(x(ta),y(a[1]));c.lineTo(x(tb),y(b[1]));c.stroke();
   points.push({x:x(tb),y:y(b[1]),time:tb,speed:b[2],name:'Observed · '+site.name});
  }
  if(seen)count++;
 }
 c.restore();el('coverage').textContent=`${count} visible recorded fragments · Observations only · Window ${clock(view[0])}–${clock(view[1])} ${regionName} time. `+sites.map(s=>`${s.name}: ${s.frames} sampled frames`).join(' · ');
}

function renderMovements(sites){
 const host=el('movement-summary');if(!host)return;host.replaceChildren();
 for(const site of sites){
  const title=document.createElement('h3');title.textContent=site.name;host.append(title);
  const summary=site.movement_summary;if(!summary){host.append(document.createTextNode('Collecting movement evidence.'));continue;}
  const note=document.createElement('p');note.textContent=`${summary.unknown_tracks} incomplete/ambiguous tracks excluded from spatial matching; ${summary.phase_samples} recorded phase snapshots. Geometry and phase assignments are estimates.`;host.append(note);
  const table=document.createElement('table'),head=document.createElement('tr');
  for(const label of ['From → To','Turn','Classified fragments','Corridor role','Phase mapping']){const th=document.createElement('th');th.textContent=label;head.append(th);}table.append(head);
  for(const m of summary.movements){const row=document.createElement('tr');for(const value of [m.from+' → '+m.to,m.turn,m.observed_tracks,(['E','W'].includes(m.from)?(['E','W'].includes(m.to)?'Through · both links':'Exiting · previous link only'):(['E','W'].includes(m.to)?'Entering · next link only':'Cross street · no corridor link')),m.phase_numbers.length?'EST phase '+m.phase_numbers.join(', '):'Not decoded · '+m.qualifying_releases+' releases']){const cell=document.createElement('td');cell.textContent=value;row.append(cell);}table.append(row);}host.append(table);
 }
}
function zoom(f,fraction=.5){
 if(!data||!view)return;
 fraction=Math.max(0,Math.min(1,fraction));
 const total=data.end-data.start;if(total<=0)return;
 const oldSpan=view[1]-view[0],span=Math.min(total,Math.max(Math.min(20,total),oldSpan*f));
 // Keep the time underneath the pointer at the same horizontal position.
 const anchor=view[0]+fraction*oldSpan,start=Math.max(data.start,Math.min(data.end-span,anchor-fraction*span));
 view=[start,start+span];draw();
}
async function refresh(){if(data&&Date.now()/1000-data.start>5400){data=null;points=[];el('plot').getContext('2d').clearRect(0,0,el('plot').width,el('plot').height);el('coverage').textContent='Expired snapshot hidden.';}try{const r=await fetch(`/api/${corridor}-rolling`);if(!r.ok)throw Error('Viewer unavailable');const next=await r.json();if(next.state!=='ready'){el('message').textContent=next.message;if(next.state==='expired'){data=null;points=[];el('plot').getContext('2d').clearRect(0,0,el('plot').width,el('plot').height);el('coverage').textContent='Expired snapshot hidden.';}return;}
 el('message').textContent=`Figure updated ${clock(next.generated_at)} · Next update ${clock(next.next_update)} ${regionName} time. Shows ${clock(next.start)}–${clock(next.end)}; early collection may cover less than one hour.`;
 if(next.generated_at===version)return;version=next.generated_at;const chosen=new Set([...el('sites').querySelectorAll('input:checked')].map(n=>n.value));data=next;view=[data.start,data.end];el('sites').replaceChildren();for(const s of data.sites){const label=document.createElement('label'),box=document.createElement('input');box.type='checkbox';box.value=s.id;box.checked=!chosen.size||chosen.has(s.id);box.onchange=draw;label.append(box,document.createTextNode(' '+s.name));el('sites').append(label);}draw();
 }catch(e){el('message').textContent=e.message;}}
if(el('spatial-estimates'))el('spatial-estimates').onchange=draw;
el('direction').onchange=draw;el('objects').onchange=draw;el('zoom-in').onclick=()=>zoom(.5);el('zoom-out').onclick=()=>zoom(2);el('reset').onclick=()=>{if(data){view=[data.start,data.end];draw();}};
el('time').oninput=()=>{if(data){const span=view[1]-view[0],start=data.start+(data.end-data.start-span)*Number(el('time').value)/1000;view=[start,start+span];draw();}};
el('plot').addEventListener('wheel',e=>{e.preventDefault();if(!e.deltaY)return;const canvas=el('plot'),rect=canvas.getBoundingClientRect();if(rect.width<=0||canvas.clientWidth<=110)return;const pointerX=(e.clientX-rect.left)*canvas.clientWidth/rect.width;zoom(e.deltaY>0?1.25:.8,(pointerX-90)/(canvas.clientWidth-110));},{passive:false});el('plot').ondblclick=()=>el('reset').click();
el('plot').onmousemove=e=>{const rect=el('plot').getBoundingClientRect(),x=e.clientX-rect.left,y=e.clientY-rect.top;let best=null,dist=64;for(const p of points){const d=(p.x-x)**2+(p.y-y)**2;if(d<dist){dist=d;best=p;}}el('hover').textContent=best?`${best.name} · ${clock(best.time)} · ${best.speed.toFixed(1)} m/s`:'Hover over a trajectory for its time and speed.';};window.addEventListener('resize',draw);refresh();setInterval(refresh,15000);

if(el("additional-matches"))el("additional-matches").onchange=draw;
