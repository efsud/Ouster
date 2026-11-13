'use strict';
const el = id => document.getElementById(id);
const canvas = el('speed'), ctx = canvas.getContext('2d');
const formatter = new Intl.DateTimeFormat('en-US', {timeZone:'America/New_York',
  month:'short', day:'numeric', hour:'2-digit', minute:'2-digit', second:'2-digit',
  hourCycle:'h23', timeZoneName:'short'});
const fmt = t => formatter.format(t * 1000);
const short = t => formatter.formatToParts(t * 1000)
  .filter(p=>['hour','minute','second'].includes(p.type)).map(p=>p.value).join(':');
const color = speed => `hsl(${Math.round(Math.max(0,Math.min(speed,90))/90*24)*5},78%,39%)`;
let index, view, bounds, shownCapture, drawing = 0, hoverGrid = new Map(), cache = new Map();
let ready = false, frame = 0;
const plot = {left:64, right:0, top:103, bottom:437};
const clamp = (n,l,h) => Math.max(l,Math.min(h,n));

function schedule(){
  if (!frame) frame=requestAnimationFrame(()=>{frame=0;draw();});
}
function setView(start, span) {
  if (!bounds) return;
  const total = bounds[1]-bounds[0];
  span = clamp(span,Math.min(10,total),total);
  start=clamp(start,bounds[0],bounds[1]-span);
  view=[start,start+span];
  schedule();
}
function zoom(factor,anchor=.5){
  if (!view) return;
  const old=view[1]-view[0], span=clamp(old*factor,10,bounds[1]-bounds[0]);
  setView(view[0]+(old-span)*anchor,span);
}
function reset(){ if(bounds) setView(bounds[0],bounds[1]-bounds[0]); }
function resize(){
  const width = Math.round(canvas.clientWidth), height = Math.round(canvas.clientHeight);
  const dpr=window.devicePixelRatio||1;
  canvas.width=width*dpr;canvas.height=height*dpr;
  ctx.setTransform(dpr,0,0,dpr,0,0);
  ctx.fillStyle='#fff';ctx.fillRect(0,0,width,height);
  plot.right=width-18;plot.bottom=height-70;
  return width;
}
function empty(message){
  ready=false;hoverGrid.clear();resize();ctx.font='14px system-ui';ctx.fillStyle='#43596d';
  ctx.fillText(message,12,45,canvas.clientWidth-25);
  el('plot-status').textContent=message;
  el('export').disabled=true;
}
function getTracks(id){
  if(!cache.has(id)) cache.set(id,fetch(`/api/observed/${index.capture_id}/${id}`).then(r=>{
    if(!r.ok)throw Error('Could not read saved fragments for '+id);
    return r.json();
  }).catch(e=>{cache.delete(id);throw e;}));
  return cache.get(id);
}
function setup(data){
  index=data;bounds=[data.start,data.end];view=[...bounds];cache=new Map();
  el('time-reset').textContent=data.end-data.start===3600?'Full hour':'Full recording';
  el('sites').replaceChildren();
  for(const s of index.sites){
    const label=document.createElement('label'), box=document.createElement('input');
    box.type='checkbox';box.value=s.id;box.checked=true;
    box.onchange=schedule;label.append(box,document.createTextNode(' '+s.name));el('sites').append(label);
  }
  const select=el('objects');
  select.replaceChildren(new Option('Vehicles','vehicles'),new Option('All SDK types','all'));
  const codes=new Set([...Object.keys(data.classes),...data.sites.flatMap(s=>Object.keys(s.object_classes))]);
  for(const code of codes)select.append(new Option(`${data.classes[code]||'Unknown class'} · SDK ${code}`,code));
  schedule();
}
async function draw(){
  const id=++drawing;
  if(!index){empty('No completed Florida figure yet.');return;}
  ready=false;el('export').disabled=true;
  const active=new Set([...el('sites').querySelectorAll('input:checked')].map(v=>v.value));
  const sites=index.sites.filter(s=>active.has(s.id));
  const [start,end]=view, span=end-start;
  const slider=el('time-position');
  slider.max=Math.max(0,bounds[1]-bounds[0]-span);
  slider.value=start-bounds[0];slider.disabled=Number(slider.max)===0;
  el('zoom-in').disabled=span<=10;el('zoom-out').disabled=span>=bounds[1]-bounds[0];
  if(!sites.length){empty('Select one or more intersections.');return;}
  if(!sites.some(s=>s.frames)){
    empty('No saved frames for these sensors. See the reception results below.');return;
  }
  let series;
  try{ series=await Promise.all(sites.map(s=>getTracks(s.id))); }
  catch(e){if(id===drawing)empty(e.message);return;}
  if(id!==drawing)return;
  const width=resize();
  const object=el('objects').value, direction=el('direction').value;
  const {left,right,top,bottom}=plot;
  const min=index.sites[0].station_m-150,max=index.sites.at(-1).station_m+150;
  const x=t=>left+(t-start)/span*(right-left);
  const y=m=>bottom-(m-min)/(max-min)*(bottom-top);
  canvas.dataset.start=start;canvas.dataset.end=end;
  ctx.textAlign='left';ctx.fillStyle='#152a3d';ctx.font='bold 15px system-ui';
  ctx.fillText('SR-436 · observed segment speeds',12,21,width-24);
  ctx.font='11px system-ui';
  ctx.fillText(`${fmt(start)} – ${fmt(end)} · America/New_York`,12,40,width-24);
  ctx.fillText('Approx. station (m) · Cranes Roost = 0',12,59,width-24);
  const bar=Math.min(176,width-130);
  for(let i=0;i<25;i++){
    ctx.fillStyle=color(i*90/24);ctx.fillRect(left+i*bar/25,73,bar/25+1,7);
  }
  ctx.fillStyle='#152a3d';ctx.fillText('0',left,94);ctx.fillText('45',left+bar*.46,94);
  ctx.fillText('≥90 km/h',left+bar-31,94);
  const ticks=width<550?3:6;
  for(let i=0;i<=ticks;i++){
    const t=start+span*i/ticks, xx=x(t);
    ctx.strokeStyle='#e0e8ef';ctx.beginPath();ctx.moveTo(xx,top);ctx.lineTo(xx,bottom);ctx.stroke();
    ctx.fillStyle='#334c60';ctx.textAlign=i===0?'left':i===ticks?'right':'center';
    ctx.fillText(short(t),xx,bottom+16);
  }
  ctx.textAlign='left';
  const groups=new Map();
  for(const site of sites){
    if(!groups.has(site.station_m))groups.set(site.station_m,[]);
    groups.get(site.station_m).push(site.name.split(' & ')[0]);
  }
  for(const [m,names] of groups){
    const yy=y(m);
    ctx.strokeStyle='#dbe4eb';ctx.setLineDash([3,4]);ctx.beginPath();
    ctx.moveTo(left,yy);ctx.lineTo(right,yy);ctx.stroke();ctx.setLineDash([]);
    ctx.fillStyle='#4b6175';ctx.fillText(Math.round(m)+' m',7,yy+4);
    ctx.fillText(names.join(' / '),left+3,yy-4,right-left-8);
  }
  ctx.fillText('Receipt time · America/New_York',left,bottom+35);
  ctx.fillText('Signal-station placement if uncalibrated · no estimated vehicles',left,bottom+52,right-left);
  hoverGrid=new Map();
  const lines=new Map();
  let segments=0;
  const vehicles=new Set(index.vehicles);
  for(let i=0;i<series.length;i++){
    const site=sites[i];
    for(const [code,dir,pairs] of series[i]){
      if((direction!=='all'&&dir!==direction)||(object==='vehicles'&&!vehicles.has(code))||
          (!['all','vehicles'].includes(object)&&code!==object))continue;
      if(pairs[0][0]+index.start>end||pairs.at(-1)[2]+index.start<start)continue;
      for(const [from,station0,to,station1,speed] of pairs){
        const t0=index.start+from,t1=index.start+to;
        if(t1<start||t0>end)continue;
        const x0=x(t0),x1=x(t1),y0=y(station0),y1=y(station1),shade=color(speed);
        if(!lines.has(shade))lines.set(shade,new Path2D());
        const path=lines.get(shade);path.moveTo(x0,y0);path.lineTo(x1,y1);segments++;
        if(x1>=left&&x1<=right&&y1>=top&&y1<=bottom){
          const k=`${Math.floor(x1/8)},${Math.floor(y1/8)}`;
          if(!hoverGrid.has(k))hoverGrid.set(k,{x:x1,y:y1,t:t1,speed,station:station1,name:site.name,code,dir});
        }
      }
    }
  }
  ctx.save();ctx.beginPath();ctx.rect(left,top,right-left,bottom-top);ctx.clip();
  ctx.lineWidth=1.35;ctx.globalAlpha=.83;
  for(const [shade,path] of lines){ctx.strokeStyle=shade;ctx.stroke(path);}
  ctx.restore();
  const unc=sites.filter(s=>s.frames&&!s.calibrated_projection).length;
  el('plot-status').textContent=`${segments.toLocaleString()} observed segments · ${fmt(start)} to ${fmt(end)}.`+
    (unc?` ${unc} selected sensors lack calibration; their speed strips have unknown direction.`:'')+
    (!segments?' No observations match the current filters.':'');
  canvas.dataset.segments=segments;
  ready=true;el('export').disabled=false;
}
canvas.addEventListener('wheel',e=>{
  if(!view)return;
  e.preventDefault();
  zoom(e.deltaY<0?.8:1.25,clamp((e.offsetX-plot.left)/(plot.right-plot.left),0,1));
},{passive:false});
canvas.addEventListener('dblclick',reset);
canvas.addEventListener('pointermove',e=>{
  const gx=Math.floor(e.offsetX/8),gy=Math.floor(e.offsetY/8);
  let best=null, distance=100;
  for(let dx=-2;dx<=2;dx++)for(let dy=-2;dy<=2;dy++){
    const p=hoverGrid.get(`${gx+dx},${gy+dy}`);
    if(!p)continue;
    const d=(p.x-e.offsetX)**2+(p.y-e.offsetY)**2;
    if(d<distance){distance=d;best=p;}
  }
  el('hover').textContent=best?`${best.name} · ${fmt(best.t)} · ${best.speed.toFixed(1)} km/h · ${best.station.toFixed(1)} m · ${index.classes[best.code]||'Unknown SDK class'} · ${best.dir}`:'Move over a segment to inspect it.';
});
el('zoom-in').onclick=()=>zoom(.5);el('zoom-out').onclick=()=>zoom(2);el('time-reset').onclick=reset;
el('time-position').oninput=e=>setView(bounds[0]+Number(e.target.value),view[1]-view[0]);
el('direction').onchange=schedule;el('objects').onchange=schedule;
el('export').onclick=()=>{if(ready)canvas.toBlob(blob=>{
  if(!blob)return;
  const a=document.createElement('a');a.href=URL.createObjectURL(blob);
  a.download=`sr436-observed-${index.capture_id}.png`;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);
},'image/png');};
window.addEventListener('resize',schedule);

async function refresh(){
  try{
    const r=await fetch('/api/status');if(!r.ok)throw Error('Local capture status unavailable.');
    const s=await r.json();
    if(s.observed&&shownCapture!==s.capture_id){
      const response=await fetch('/api/observed/index.json');
      if(!response.ok)throw Error('Observed archive is not ready.');
      const data=await response.json();
      if(data.capture_id===s.capture_id){setup(data);shownCapture=s.capture_id;}
    }else if(!s.observed&&index){
      index=view=bounds=shownCapture=null;el('sites').replaceChildren();schedule();
    }
    const state=s.state==='no_reception'?'No frames received. Review each sensor below.':
      s.state==='not_started'?'No Florida capture started. Open the private recording launcher.':
      `Capture ${s.state.replaceAll('_',' ')} · ${fmt(s.start)} to ${fmt(s.end)}.`;
    el('recording-status').textContent=state;
    const opened = new Set([...el('reception').querySelectorAll('details[open]')].map(d=>d.dataset.site));
    el('reception').replaceChildren();
    for(const site of s.sites){
      const q=index?.sites.find(v=>v.id===site.id);
      const row=document.createElement('tr');
      const status=site.unavailable||((site.last_frame&&Date.now()/1000-site.last_frame<5&&
        ['recording','checking_reception'].includes(s.state))?'Fresh FRAME received':site.state||'Not started');
      for(const value of [`${site.name} · ${site.id}`,status,q?.frames??site.frames??0,
        q?.first_receipt?`${fmt(q.first_receipt)} – ${fmt(q.last_receipt)} (${q.receipt_span_s.toFixed(1)} s)`:'—',
        q?.gaps_over_3s??'—',q?`${q.longest_gap_s.toFixed(1)} s`:'—']){
        const td=document.createElement('td');td.textContent=value;row.append(td);
      }
      const td=document.createElement('td');
      if(q){
        const detail=document.createElement('details'), summary=document.createElement('summary');
        summary.textContent='Show audit';detail.dataset.site=site.id;detail.open=opened.has(site.id);detail.append(summary);
        const pre=document.createElement('pre');pre.textContent=JSON.stringify({
          sensor_timestamps:[q.first_sensor_timestamp,q.last_sensor_timestamp], sessions:q.sessions,
          classes:q.object_classes, diagnostics:q.diagnostics, gaps:q.gaps, archive_issues:q.archive_issues
        },null,2);
        detail.append(pre);td.append(detail);
      }else td.textContent='—';
      row.append(td);el('reception').append(row);
    }
  }catch(e){el('recording-status').textContent=e.message;}
}
empty('No completed Florida figure yet.');
refresh();setInterval(refresh,5000);
