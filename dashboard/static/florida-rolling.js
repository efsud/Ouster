'use strict';
const el=id=>document.getElementById(id),vehicle=new Set(['1','2','3','4','5','6','7','8','9','15']);
const corridor=document.body.dataset.corridor||'florida',regionName=corridor==='finch'?'Toronto':'Florida';
let data=null,view=null,points=[],version=0,reconstruction=null,colorExample=null,overlapExample=null;
let aggregateCache=null,aggregateRects=[];
const isAggregate=()=>Boolean(el('aggregate-mode')?.checked);
if(el('aggregate-mode'))el('aggregate-mode').checked=new URLSearchParams(location.search).get('aggregate')==='1';
if(new URLSearchParams(location.search).get('between')==='1'&&el('between-layer'))el('between-layer').checked=true;
const clock=t=>new Date(t*1000).toLocaleTimeString('en-CA',{timeZone:corridor==='finch'?'America/Toronto':'America/New_York',hour12:false});
function color(v){const t=Math.max(0,Math.min(1,v/20));return `hsl(${t*120},75%,40%)`;}
function aggregateModeUI(){
 const active=isAggregate();
 for(const id of ['aggregate-options','aggregate-note','aggregate-legend'])if(el(id))el(id).hidden=!active;
 if(el('reconstruction-controls'))el('reconstruction-controls').hidden=active;
 if(el('plot-caption'))el('plot-caption').textContent=active?'Colored cells summarize retained observations; individual lines and estimated connections are hidden.':'Solid lines show recorded positions; any timing corrections are noted above. Dashed layers estimate missing positions. Missing evidence stays blank.';
 if(el('plot-explanation'))el('plot-explanation').textContent=active?'Speed is averaged once per sensor/session/object within each cell, then equally across those objects. Counts are sensor-local tracked IDs, not corridor flow or density. Short and wholly stationary tracks may be absent from the retained data. Gray means no retained observations—not necessarily no traffic or a sensor outage.':'Red = slow, yellow = about 10 m/s, green = 20+ m/s. Colors show observed or estimated speed, not signal state. Samples are taken at up to 2 Hz. Observed lines stop at gaps longer than 1.5 seconds. Supported missing portions can be shown using the separate estimate layers.';
 el('plot').setAttribute('aria-label',active?'Florida time-distance cells colored by mean observed speed':'Time-distance trajectories colored by speed');
 el('hover').textContent=active?'Hover over a colored cell for mean speed and observation support.':'Hover over a trajectory for its time and speed.';
}
function paintAggregate(c,x,y,sites,w,h){
 const dt=Number(el('aggregate-time').value),dx=Number(el('aggregate-space').value);
 const key=JSON.stringify([version,sites.map(s=>s.id),el('direction').value,el('objects').value,dt,dx]);
 if(aggregateCache?.key!==key)aggregateCache={key,...TrajectoryAggregation.build(sites,{direction:el('direction').value,objects:el('objects').value,timeBinSeconds:dt,spaceBinMeters:dx,start:0,end:data.end-data.start})};
 c.fillStyle='#e9eef2';c.fillRect(90,20,w-110,h-70);aggregateRects=[];
 const overlapping=new Map();
 for(const cell of aggregateCache.cells){
  if(data.start+cell.timeEnd<=view[0]||data.start+cell.timeStart>=view[1])continue;
  const bin=cell.timeStart+':'+cell.spaceStart;
  if(!overlapping.has(bin))overlapping.set(bin,[]);overlapping.get(bin).push(cell);
 }
 const names=new Map(sites.map(s=>[s.id,s.name]));let visible=0,sparse=0;
 for(const cells of overlapping.values()){
  cells.sort((a,b)=>a.site.localeCompare(b.site));
  cells.forEach((cell,i)=>{
   const left=x(data.start+cell.timeStart),right=x(data.start+cell.timeEnd),part=(right-left)/cells.length;
   const x0=left+i*part,x1=left+(i+1)*part,y0=y(cell.spaceEnd),y1=y(cell.spaceStart);
   if(Math.min(w-20,x1)<=Math.max(90,x0)||Math.min(h-50,y1)<=Math.max(20,y0))return;
   c.fillStyle=color(cell.speed);c.fillRect(x0,y0,x1-x0,y1-y0);
   aggregateRects.push({x0:Math.max(90,x0),x1:Math.min(w-20,x1),y0:Math.max(20,y0),y1:Math.min(h-50,y1),cell,name:names.get(cell.site),overlap:cells.length});
   visible++;if(cell.objectCount===1)sparse++;
  });
 }
 el('aggregate-note').textContent=`${dt}-second × ${dx}-m fixed cells · mean observed speed · ${visible.toLocaleString()} visible sensor cells (${sparse.toLocaleString()} supported by one ID). Zoom keeps the same bins. Where sensors overlap, side-by-side strips retain separate sensor summaries.`;
 return visible;
}
function draw(){
 if(!data)return;const panRange=data.end-data.start-(view[1]-view[0]);el('time').value=panRange>0?1000*(view[0]-data.start)/panRange:0;const selected=new Set([...el('sites').querySelectorAll('input:checked')].map(n=>n.value)),sites=data.sites.filter(s=>selected.has(s.id));
 renderMovements(sites);
 const canvas=el('plot'),w=canvas.clientWidth,h=650,dpr=window.devicePixelRatio||1;canvas.width=w*dpr;canvas.height=h*dpr;const c=canvas.getContext('2d');c.scale(dpr,dpr);c.clearRect(0,0,w,h);points=[];aggregateRects=[];
 if(!sites.length){c.fillText('Select an intersection.',30,40);return;}
 const lo=Math.min(...sites.map(s=>s.station_m))-130,hi=Math.max(...sites.map(s=>s.station_m))+130;
 const x=t=>90+(t-view[0])/(view[1]-view[0])*(w-110),y=s=>h-50-(s-lo)/(hi-lo)*(h-80);
 c.font='12px sans-serif';c.fillStyle='#52636d';c.strokeStyle='#dbe3e8';
 const ticks=Math.max(2,Math.min(6,Math.floor((w-110)/100)));
 for(let i=0;i<=ticks;i++){const t=view[0]+i*(view[1]-view[0])/ticks;c.beginPath();c.moveTo(x(t),20);c.lineTo(x(t),h-50);c.stroke();c.textAlign=i===0?'left':i===ticks?'right':'center';c.fillText(clock(t),x(t),h-25);}c.textAlign='left';
 for(const s of sites){c.fillStyle='#263b46';c.fillText(s.name,95,y(s.station_m)-8);c.fillText(Math.round(s.station_m)+' m',4,y(s.station_m));c.strokeStyle='#c3cdd3';c.beginPath();c.moveTo(90,y(s.station_m));c.lineTo(w-20,y(s.station_m));c.stroke();}
 c.save();c.beginPath();c.rect(90,20,w-110,h-70);c.clip();let count=0;
 if(isAggregate()){
  count=paintAggregate(c,x,y,sites,w,h);c.restore();
  for(const s of sites){c.strokeStyle='rgba(38,59,70,.45)';c.beginPath();c.moveTo(90,y(s.station_m));c.lineTo(w-20,y(s.station_m));c.stroke();c.fillStyle='rgba(255,255,255,.9)';c.fillRect(93,y(s.station_m)-23,c.measureText(s.name).width+8,18);c.fillStyle='#263b46';c.fillText(s.name,97,y(s.station_m)-9);}
  el('coverage').textContent=`${count.toLocaleString()} visible aggregated sensor cells · Window ${clock(view[0])}–${clock(view[1])} ${regionName} time · ${sites.length} selected intersections. Estimated paths are excluded.`;
  return;
 }
 for(const site of sites)for(const tr of site.tracks){
  const filter=el('objects').value,code=tr.class_type;if(tr.direction!==el('direction').value)continue;
  if(filter==='vehicles'&&!vehicle.has(code)||filter==='pedestrians'&&!['0','10','11','14','16'].includes(code)||filter==='cyclists'&&!['12','13','17'].includes(code))continue;
  if(tr.method)continue;
  let seen=false;const overlapSelected=overlapExample?.sites.includes(site.id)&&overlapExample.source_keys.some(k=>JSON.stringify(k)===JSON.stringify(tr.source_key));
  for(let i=1;i<tr.points.length;i++){
   const a=tr.points[i-1],b=tr.points[i],ta=data.start+a[0],tb=data.start+b[0],dt=b[0]-a[0];
   if(dt<=0||dt>1.5||tb<view[0]||ta>view[1])continue;
   seen=true;c.strokeStyle=color(b[2]);c.lineWidth=overlapSelected?3:1;c.setLineDash([]);
   c.beginPath();c.moveTo(x(ta),y(a[1]));c.lineTo(x(tb),y(b[1]));c.stroke();
   const receiptTime=data.start+(tr.original_receipt_offsets_s?.[i]??b[0]);
   points.push({x:x(tb),y:y(b[1]),time:tb,receiptTime,speed:b[2],name:'Observed position · '+site.name+(overlapSelected?' · overlap correspondence hypothesis; identity unverified':'')});
  }
  if(seen)count++;
 }
 paintReconstruction(c,x,y,selected);
 c.restore();el('coverage').textContent=`${count} visible recorded fragments · Window ${clock(view[0])}–${clock(view[1])} ${regionName} time. `+sites.map(s=>`${s.name}: ${s.frames} plotted frames / ${s.raw_frames??s.frames} received frames`).join(' · ');
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
 if(next.time_basis==='receipt_debursted'){
  const audits=next.sites.flatMap(s=>s.clock_audit||[]),events=audits.flatMap(a=>a.events||[]);
  el('message').textContent+=` Timing: ${events.length} bounded delivery bursts corrected using continuous sensor elapsed time between receipt anchors. Positions are measured; adjusted times are estimates. Hover to compare receipt time. Cross-sensor clock offsets remain unverified.`;
 }
 if(next.generated_at===version)return;version=next.generated_at;const chosen=new Set([...el('sites').querySelectorAll('input:checked')].map(n=>n.value));data=next;overlapExample=null;view=[data.start,data.end];el('sites').replaceChildren();for(const s of data.sites){const label=document.createElement('label'),box=document.createElement('input');box.type='checkbox';box.value=s.id;box.checked=!chosen.size||chosen.has(s.id);box.onchange=draw;label.append(box,document.createTextNode(' '+s.name));el('sites').append(label);}draw();refreshReconstruction();
 }catch(e){el('message').textContent=e.message;}}
if(el('spatial-estimates'))el('spatial-estimates').onchange=draw;
for(const id of ['aggregate-mode','aggregate-time','aggregate-space'])if(el(id))el(id).onchange=()=>{
 aggregateModeUI();
 const url=new URL(location.href);if(isAggregate())url.searchParams.set('aggregate','1');else url.searchParams.delete('aggregate');history.replaceState(null,'',url);
 draw();
};
aggregateModeUI();
el('direction').onchange=draw;el('objects').onchange=draw;el('zoom-in').onclick=()=>zoom(.5);el('zoom-out').onclick=()=>zoom(2);el('reset').onclick=()=>{if(data){view=[data.start,data.end];draw();}};
el('time').oninput=()=>{if(data){const span=view[1]-view[0],start=data.start+(data.end-data.start-span)*Number(el('time').value)/1000;view=[start,start+span];draw();}};
el('plot').addEventListener('wheel',e=>{e.preventDefault();if(!e.deltaY)return;const canvas=el('plot'),rect=canvas.getBoundingClientRect();if(rect.width<=0||canvas.clientWidth<=110)return;const pointerX=(e.clientX-rect.left)*canvas.clientWidth/rect.width;zoom(e.deltaY>0?1.25:.8,(pointerX-90)/(canvas.clientWidth-110));},{passive:false});el('plot').ondblclick=()=>el('reset').click();
el('plot').onmousemove=e=>{const rect=el('plot').getBoundingClientRect(),x=e.clientX-rect.left,y=e.clientY-rect.top;
 if(!data){el('hover').textContent='Waiting for recorded observations.';return;}
 if(isAggregate()){
  const hit=aggregateRects.find(r=>x>=r.x0&&x<r.x1&&y>=r.y0&&y<r.y1);
  el('hover').textContent=hit?`${hit.name} · ${clock(data.start+hit.cell.timeStart)}–${clock(data.start+hit.cell.timeEnd)} · ${hit.cell.spaceStart}–${hit.cell.spaceEnd} m · mean ${hit.cell.speed.toFixed(1)} m/s · ${hit.cell.objectCount} sensor-local IDs · ${hit.cell.sampleCount} observations`+(hit.overlap>1?` · ${hit.overlap} sensors share this cell; strips are separate summaries`:''):'No retained observations in this cell; this does not establish zero traffic.';
  return;
 }
 let best=null,dist=64;for(const p of points){const d=(p.x-x)**2+(p.y-y)**2;if(d<dist){dist=d;best=p;}}el('hover').textContent=best?`${best.name} · ${clock(best.time)} · ${best.speed.toFixed(1)} m/s`+(best.receiptTime!=null&&Math.abs(best.receiptTime-best.time)>.05?` · adjusted time; received ${clock(best.receiptTime)} (${(best.receiptTime-best.time).toFixed(2)} s later)`:''):'Hover over a trajectory for its time and speed.';};window.addEventListener('resize',draw);refresh();setInterval(refresh,15000);

if(el("additional-matches"))el("additional-matches").onchange=draw;
function showColorExample(kind){
 const paths=reconstruction?.residual_color?.[kind]||[];
 const candidates=paths.filter(p=>p.direction===el('direction').value);
 const p=candidates.sort((a,b)=>(b.points.at(-1)[0]-b.points[0][0])-(a.points.at(-1)[0]-a.points[0][0]))[0]||paths[0];
 if(!p||!data)return;
 overlapExample=null;
 el('direction').value=p.direction;el('objects').value='vehicles';el('color-layer').checked=true;
 el(kind==='within_intersection'?'within-layer':'between-layer').checked=true;
 const sites=new Set(p.sites||[p.site]);for(const box of el('sites').querySelectorAll('input'))box.checked=sites.has(box.value);
 const start=data.start+p.points[0][0],end=data.start+p.points.at(-1)[0],padding=Math.max(10,(end-start)*.2);
 view=[Math.max(data.start,start-padding),Math.min(data.end,end+padding)];colorExample=p.points[0][0]+':'+p.points.at(-1)[0];draw();
}
if(el('color-local-example'))el('color-local-example').onclick=()=>showColorExample('within_intersection');
if(el('color-between-example'))el('color-between-example').onclick=()=>showColorExample('between_intersections');
if(el('overlap-example'))el('overlap-example').onclick=()=>{
 const link=reconstruction?.coverage_audit?.overlap_links?.find(l=>l.example&&l.direction===el('direction').value);if(!link||!data)return;
 overlapExample={...link.example,sites:link.sites};el('objects').value='vehicles';
 for(const box of el('sites').querySelectorAll('input'))box.checked=link.sites.includes(box.value);
 view=[Math.max(data.start,data.start+link.example.overlap_time[0]-8),Math.min(data.end,data.start+link.example.overlap_time[1]+8)];
 draw();el('plot').scrollIntoView({block:'center'});
};

function renderGapAudit(audit){
 const host=el('coverage-audit');if(!host)return;host.replaceChildren();
 if(!audit){host.textContent='Waiting for an audit aligned with this figure window.';return;}
 const note=document.createElement('p');note.textContent='Whole-window audit, both directions. Local counts cover vehicle classes with observed same-session/object endpoints; the baseline corridor matcher currently covers cars. Entirely unseen vehicles and changed IDs are not counted. Estimated paths are excluded from measured KPI inputs. Cross-sensor travel times remain experimental.';host.append(note);
 function table(headers,rows){const t=document.createElement('table'),h=document.createElement('tr');for(const label of headers){const cell=document.createElement('th');cell.textContent=label;h.append(cell);}t.append(h);for(const values of rows){const r=document.createElement('tr');for(const value of values){const cell=document.createElement('td');cell.textContent=value;r.append(cell);}t.append(r);}host.append(t);}
 table(['Intersection','Observable same-ID gaps','Baseline filled','Experimental filled','Unresolved'],audit.sites.map(s=>[s.name,s.observable_same_id_gaps,s.baseline_estimated,s.experimental_estimated,s.unresolved]));
 for(const s of audit.sites){const p=document.createElement('p');p.textContent=s.name+': '+Object.entries(s.unresolved_reasons).map(([k,v])=>`${k.replaceAll('_',' ')}: ${v}`).join('; ')+`. Classified exit fragments: ${s.movement_roles.corridor_exit||0}; unknown movement fragments: ${s.movement_roles.unknown||0}. Exit classifications are provisional; unknowns are not treated as exits.`;host.append(p);}
 table(['Link','Direction','Eligible departures','Baseline estimated','Still unmatched departures','Additional experimental proposals'],audit.links.map(l=>[l.names.join(' → '),l.direction,l.eligible_departures,l.baseline_estimated,l.baseline_unmatched_departures,l.experimental_estimated]));
 if(audit.overlap_links){
  const label=document.createElement('p');label.textContent='Observed coverage overlap: negative median end-to-start distance means the views overlap, so a forward dashed gap would be inappropriate. Concurrent motion/size matches are identity hypotheses, not recovered missing samples.';host.append(label);
  table(['Adjacent views','Direction','Median end-to-start distance','Overlap association hypotheses'],audit.overlap_links.map(l=>[l.names.join(' → '),l.direction,l.median_signed_end_to_start_m==null?'Unavailable':l.median_signed_end_to_start_m.toFixed(1)+' m',l.overlap_hypotheses]));
 }
 const caveat=document.createElement('p');caveat.textContent='Link counts are fragment endpoints, not unique vehicles. The experimental layer can use a different class pool and does not reduce the baseline unmatched count. Unknown movements, clock conflicts and ambiguous identities remain unresolved; a fully connected drawing would not prove accurate KPIs.';host.append(caveat);
}

function paintReconstruction(c,x,y,selected){
 if(!reconstruction||reconstruction.state!=='ready'||reconstruction.snapshot_generated_at!==data.generated_at)return;
 const counts=[0,0],extraCounts=[0,0],allowed=['all','vehicles'].includes(el('objects').value);
 const groups=[['within-layer',reconstruction.within_intersection||[],0],['between-layer',reconstruction.between_intersections||[],1]];
 if(el('color-layer')?.checked&&reconstruction.residual_color){
  groups.push(['within-layer',reconstruction.residual_color.within_intersection||[],0],['between-layer',reconstruction.residual_color.between_intersections||[],1]);
 }
 for(const [control,paths,group] of groups){if(!allowed||!el(control)?.checked)continue;
  for(const path of paths){
   if(path.direction!==el('direction').value||!(path.sites||[path.site]).every(id=>selected.has(id)))continue;
   let seen=false,distance=0;
   for(let i=1;i<path.points.length;i++){
    const a=path.points[i-1],b=path.points[i],ta=data.start+a[0],tb=data.start+b[0],length=Math.hypot(x(tb)-x(ta),y(b[1])-y(a[1]));
    if(tb>=view[0]&&ta<=view[1]){seen=true;c.strokeStyle=color(b[2]);c.lineWidth=path.layer==='residual_color_slope'&&colorExample===path.points[0][0]+':'+path.points.at(-1)[0]?3:1.8;c.setLineDash(path.layer==='residual_color_slope'?[10,4,2,4]:group?[8,5]:[3,4]);c.lineDashOffset=-distance;c.beginPath();c.moveTo(x(ta),y(a[1]));c.lineTo(x(tb),y(b[1]));c.stroke();points.push({x:x(tb),y:y(b[1]),time:tb,speed:b[2],name:'EST '+(group?'between intersections · identity unverified':'within intersection'+((path.identity||'').startsWith('unverified')?' · identity unverified':''))+' · '+({'bounded_stationary_latent_position':'stationary position estimate','endpoint_envelope_grid_retry_v1':'refined endpoint time grid'}[path.estimation_model]||({'kinematic_same_id_lateral_v1':'same-ID lateral-motion estimate','color_slope_chronological_v1':'same-color constant-slope proposal'}[path.method]||path.method))+(path.exact_endpoint_interpolation===false?' · stationary estimate; endpoint residual ≤'+(100*Math.max(...(path.endpoint_position_residual_m||[0]).map(Math.abs))).toFixed(1)+' cm':'')+(path.object_id?' · object ID '+path.object_id:'')});}distance+=length;
   }if(seen){counts[group]++;if(path.layer==='residual_color_slope')extraCounts[group]++;}
  }
 }
 c.setLineDash([]);c.lineDashOffset=0;
 if(el('layer-counts'))el('layer-counts').textContent=`Visible estimates: ${counts[0]} within intersections; ${counts[1]} between intersections. Colors indicate speed, not confidence.`+(el('color-layer')?.checked?` Requested color-slope additions: ${extraCounts[0]} within; ${extraCounts[1]} between.`:'')+(el('within-layer')?.checked&&counts[0]===0?' No supported local estimates in this selection; checking the box cannot join unidentified fragments.':'');
}
async function refreshReconstruction(){
 if(!el('reconstruction-status'))return;
 try{
  const response=await fetch(`/api/${corridor}-reconstruction`);if(!response.ok)throw Error('Reconstruction study unavailable');reconstruction=await response.json();
  const aligned=reconstruction.state==='ready'&&data&&reconstruction.snapshot_generated_at===data.generated_at;
  renderGapAudit(aligned?reconstruction.coverage_audit:null);
  if(el('overlap-example'))el('overlap-example').disabled=!aligned||!reconstruction.coverage_audit?.overlap_links?.some(l=>l.example);
  for(const id of ['within-layer','between-layer'])el(id).disabled=!aligned;
  if(el('color-layer'))el('color-layer').disabled=!aligned||!reconstruction.residual_color;
  if(el('color-local-example'))el('color-local-example').disabled=!aligned||!reconstruction.residual_color?.within_intersection?.length;
  if(el('color-between-example'))el('color-between-example').disabled=!aligned||!reconstruction.residual_color?.between_intersections?.length;
  const study=reconstruction.study||{},parts=study.readiness?.partitions;
  const fallbackCounts={plateau:0,grid:0};for(const p of reconstruction.within_intersection||[]){if(p.estimation_model==='bounded_stationary_latent_position')fallbackCounts.plateau++;if(p.estimation_model==='endpoint_envelope_grid_retry_v1')fallbackCounts.grid++;}
  const lateralCount=(reconstruction.within_intersection||[]).filter(p=>p.method==='kinematic_same_id_lateral_v1').length;
  const lateralNote=lateralCount?` ${lateralCount} additional short same-ID lateral-motion estimates at sites passing masked-data checks; lane changes are unverified.`:'';
  const fallbackNote=(fallbackCounts.plateau||fallbackCounts.grid)?` Local fallbacks: ${fallbackCounts.grid} exact-endpoint grid retries; ${fallbackCounts.plateau} stationary estimates with up to 5 cm endpoint residual. Observations are unchanged.`:'';
  el('reconstruction-status').textContent=aligned?`Selected local method: ${reconstruction.method==='color_slope_chronological_v1'?'Speed-color + constant-slope chronological matching (experimental; 1 m/s color bands; original slope for 80%, bounded correction at the end)':reconstruction.method}${reconstruction.endpoint_corrected_gaps?' + bounded stationary endpoint correction on '+reconstruction.endpoint_corrected_gaps+' gaps':''}.${fallbackNote}${lateralNote}${reconstruction.association_method==='bidirectional_shape_v1'?' Matching uses forward/backward motion evidence (experimental).':''} Between-intersection transfer is experimental; identities are unverified.`:(reconstruction.message||'Waiting for layers for this figure window.')+(parts?' '+Object.entries(parts).map(([name,p])=>`${name}: ${p.tracks} usable fragments`).join(' · '):'');
  const host=el('reconstruction-comparison');host.replaceChildren();
  if(reconstruction.moderate_timing_validation){
   const v=reconstruction.moderate_timing_validation,q=v.pooled.test.methods,m=v.matching.test,p=document.createElement('p');
   p.textContent=`Smaller bounded delivery delays corrected at ${v.sites.length} qualified sites. Later hidden gaps: ${q.baseline.accepted} → ${q.moderate.accepted} reconstructed; common-case position MAE ${q.baseline.common.mae_m.toFixed(2)} → ${q.moderate.common.mae_m.toFixed(2)} m. Matching proxy: ${m.baseline.correct} → ${m.moderate.correct} correct, ${m.baseline.wrong} → ${m.moderate.wrong} wrong. Renaissance and Boston retain previous timing. These are car-trajectory interpolation checks, not verified sensor synchronization or KPI accuracy.`;host.append(p);
  }
  if(reconstruction.local_lateral_recheck){const r=reconstruction.local_lateral_recheck,p=document.createElement('p');p.textContent=`Later all-site recheck: Plaza Entrance now enabled under the unchanged short same-ID policy. Plaza later test: ${r.test.ids} distinct IDs; position MAE ${r.test.quality.mae_m.toFixed(2)} m, speed MAE ${r.test.quality.speed_mae_mps.toFixed(2)} m/s. Its earlier failed test remains recorded; Boston and Palm remain withheld for insufficient examples. This does not validate KPI values inside missing intervals.`;host.append(p);}
  if(reconstruction.residual_color){
   const v=reconstruction.residual_color,p=document.createElement('p');p.textContent=`Requested color-slope method · ${v.within_intersection.length} additional local and ${v.between_intersections.length} additional adjacent-intersection proposals across this hour. Existing estimates and observations are preserved. Departures are processed earliest first; candidates share a 1 m/s speed-color band and the closest eligible extrapolated position is selected. Ties remain unresolved.`;host.append(p);
   const limits=document.createElement('p');limits.textContent='Original slope is retained for 80% of each extension. Only the final 20% closes the endpoint discrepancy, with speed adjustment ≤0.5 m/s. Maximum gaps: 90 s locally / 120 s between sites; maximum residual: 10 m / 20 m. Local clock, session, movement and lateral checks remain active. This hypothesis layer can make wrong identity matches.';host.append(limits);
   if(v.validation){const q=v.validation.test.temporal,r=v.validation.test.spatial,line=document.createElement('p');line.textContent=`Later hidden endpoint-association test: local proposals ${q.added_correct} correct / ${q.added_wrong} wrong; spatial proposals ${r.added_correct} correct / ${r.added_wrong} wrong. The endpoint benchmark omits production local lateral/clock gates. It does not validate real cross-sensor identities.`;host.append(line);}
  }
  if(reconstruction.delivery_timing_validation){
   const v=reconstruction.delivery_timing_validation,q=v.local.test.True.methods,m=v.matching.test;
   const p=document.createElement('p');p.textContent=`Bounded delivery timing · later hidden affected gaps: ${q.receipt.accepted} → ${q.corrected.accepted} accepted. Common-gap position error ${q.receipt.common.mae_m.toFixed(2)} → ${q.corrected.common.mae_m.toFixed(2)} m. Spatial matching proxy: ${m.receipt.correct} → ${m.corrected.correct} correct, ${m.receipt.wrong} → ${m.corrected.wrong} wrong. Raw observations and receipt timestamps remain stored; clock resets, absent frames and unanchored delays remain unresolved.`;host.append(p);
  }
  if(reconstruction.gap_integrity_validation){
   const v=reconstruction.gap_integrity_validation,quiet=(reconstruction.within_intersection||[]).filter(p=>p.stationary_noise_admission).length;
   const p=document.createElement('p');p.textContent=`Gap review · ${quiet} additional quiet same-ID gaps use the stationary estimator, with at most 5 cm endpoint residual. Internal endpoints of accepted same-ID chains are excluded from between-intersection matching. Original observations stay unchanged.`;host.append(p);
   const q=v.stationary.test, t=v.terminals.test, score=document.createElement('p');score.textContent=`Later hidden-data tests: ${q.accepted} quiet-gap masks from ${q.distinct_ids} IDs, ${(q.quality.mae_m*100).toFixed(1)} cm mean position error. Fragmented matching proxy: ${t.baseline.correct} → ${t.terminals.correct} correct, ${t.baseline.wrong_identity} → ${t.terminals.wrong_identity} wrong. These conditional tests do not verify cross-sensor identities.`;host.append(score);
   const timing=document.createElement('p');timing.textContent='November 23 timing audit: the apparent interruption around 12:08 included 4–8 second receipt delays while sensor timestamps advanced only 0.1 second. '+(data?.time_basis==='receipt_debursted'?'Supported bounded delivery bursts are now corrected in newer windows; the original 12:08 raw window has expired. Unanchored delays remain unresolved.':'Receipt-time distortions remain unresolved; curves are not fabricated to hide them.');host.append(timing);
  }
  if(reconstruction.local_lateral_validation){
   const v=reconstruction.local_lateral_validation,p=document.createElement('p');
   p.textContent=`Short same-ID lateral recovery · ${v.test.accepted} additional hidden gaps, ${v.test.distinct_ids} distinct identities across ${v.enabled_sites.length} enabled intersections. Mean longitudinal error ${v.test.quality.mae_m.toFixed(2)} m; mean lateral error ${v.test.lateral_mae_m.toFixed(2)} m. Maximum gap 10 s. Other sites retain the previous method. These are masked-data checks, not verified lane changes or recovered ground truth.`;host.append(p);
  }
  if(reconstruction.bidirectional_validation){
   const v=reconstruction.bidirectional_validation,p=document.createElement('p');
   p.textContent='Bidirectional matching · later held-out interval. '+Object.entries(v.test['0.5']).map(([kind,row])=>{const old=v.test['0'][kind];return `${kind==='spatial'?'Hidden roadway sections':'Hidden time gaps'}: ${old.correct} → ${row.correct} correct; ${old.false} → ${row.false} wrong matches`;}).join('. ')+'. Same-sensor proxy tests; real cross-sensor identities are unverified. Only between-intersection matching uses this score.'+(reconstruction.local_lateral?' Local same-ID lateral recovery is evaluated separately above.':' Same-ID local reconstruction is unchanged.');host.append(p);
  }
  if(reconstruction.color_validation){
   const v=reconstruction.color_validation,p=document.createElement('p');p.textContent='Current simple method · hidden recorded gaps: '+v.summary.color_slope.accepted+'/'+v.summary.color_slope.eligible+' accepted; position MAE '+(v.summary.color_slope.mae_m?.toFixed(2)??'unavailable')+' m. Masked association: '+v.association.correct+' correct / '+v.association.matched+' matched. Real between-sensor identities remain unverified.';host.append(p);
  }
  if(reconstruction.campaign && !reconstruction.color_validation){
   const c=reconstruction.campaign,p=document.createElement('p');
   p.textContent=`Bounded validation run: ${c.state}; scheduled end ${new Date(c.deadline*1000).toLocaleString('en-CA',{timeZone:'America/Toronto'})} Toronto. This compares fixed estimators on later recorded windows; it does not force unresolved matches.`;
   host.append(p);
   for(const [method,r] of Object.entries(c.cumulative?.methods||{})){
    const row=document.createElement('p');row.textContent=`Run total · ${method}: ${r.accepted}/${r.eligible} hidden gaps reconstructed. Added-case position MAE ${r.new?.mae_m?.toFixed(2)??'unavailable'} m. Candidate comparison, not automatic deployment.`;host.append(row);
   }
   const shapes=c.cumulative?.shape_prospective;
   if(shapes?.windows){
    for(const [method,r] of Object.entries(shapes.totals)){const row=document.createElement('p');row.textContent=`Prospective masked matching · ${method==='current'?'frozen reference matcher':method==='0'?'global assignment':'size-assisted assignment'}: ${r.correct}/${r.eligible} correct matches; ${r.false} wrong. These are same-sensor masks, not verified identities between intersections.`;host.append(row);}
   }
   const gates=c.cumulative?.kinematic_gate_prospective;
   if(gates?.windows){
    for(const [method,r] of Object.entries(gates.totals)){const row=document.createElement('p');row.textContent=`Endpoint-feasibility comparison · ${method==='legacy'?'previous gate':'previous feasible-gate benchmark'}: ${r.correct}/${r.eligible} correct; ${r.false} wrong matches across ${gates.windows} future windows. Correlated same-sensor masks; actual between-sensor identities remain unverified.`;host.append(row);}
   }
   const lateral=c.cumulative?.lateral_prospective;
   if(lateral?.windows){const row=document.createElement('p');row.textContent=`Prospective lateral-motion candidate: ${lateral.accepted}/${lateral.eligible} hidden gaps reconstructed; longitudinal MAE ${lateral.quality?.mae_m?.toFixed(2)??'unavailable'} m; lateral MAE ${lateral.lateral_mae_m?.toFixed(2)??'unavailable'} m. Evaluation does not automatically enable this candidate.`;host.append(row);}
  }
  if(reconstruction.comparison){
   const note=document.createElement('p');note.textContent='Candidate comparisons below may include corrections withheld from deployment at individual sites.';host.append(note);
   for(const [method,result] of Object.entries(reconstruction.comparison)){
    const p=document.createElement('p'),m=result.common||{};p.textContent=`${method}: ${m.n||0} common held-out gaps; position MAE ${m.mae_m?.toFixed(2)??'unavailable'} m; speed MAE ${m.speed_mae_mps?.toFixed(2)??'unavailable'} m/s. Accepted ${result.accepted}/${result.eligible}.`;host.append(p);
   }
   const later=reconstruction.later_validation;
   if(later){
    const heading=document.createElement('h4');heading.textContent='Later recording · frozen model, no retraining';host.append(heading);
    for(const [method,result] of Object.entries(later.methods||{})){const p=document.createElement('p'),m=result.common||{};p.textContent=`${method}: ${m.n||0} common gaps; position MAE ${m.mae_m?.toFixed(2)??'unavailable'} m; speed MAE ${m.speed_mae_mps?.toFixed(2)??'unavailable'} m/s. Accepted ${result.accepted}/${later.sampled}.`;host.append(p);}
    const p=document.createElement('p'),coverage=later.frozen_uncertainty?.full_gap_coverage;p.textContent=`The earlier nominal 90% local error band covered ${coverage==null?'an unavailable fraction':(coverage*100).toFixed(1)+'%'} of later gaps. It is not a guaranteed confidence band and does not apply between intersections.`;host.append(p);
   }
   const integration=reconstruction.integration_validation;
   if(integration){
    const h=document.createElement('h4');h.textContent='CTM–Newell–signal experiment · hidden recorded trajectories';host.append(h);
    const labels={test_local:'Local object gap',test_outage:'All-object recording outage',test_spatial:'Spatial blind band (proxy, not between-sensor truth)'};
    for(const [key,label] of Object.entries(labels)){
     const rows=integration.results?.[key],base=rows?.current?.common,model=rows?.integrated?.common;if(!base||!model)continue;
     const p=document.createElement('p');p.textContent=`${label}: ${model.n} common accepted masks; current position MAE ${base.mae_m?.toFixed(3)??'unavailable'} m → integrated ${model.mae_m?.toFixed(3)??'unavailable'} m. Cases with all three priors: ${rows.integrated.common_all_priors??0}.`;host.append(p);
     const gain=integration.paired_gain?.[key];if(gain){const p=document.createElement('p');p.textContent=`Exploratory 95% range for mean improvement: ${gain.bootstrap95_m.map(x=>x.toFixed(3)).join(' to ')} m; positive means improvement.`;host.append(p);}
    }
    const p=document.createElement('p');p.textContent='Experimental soft priors, provisional lane/stop-line geometry. This integrated-prior experiment did not demonstrate reliable improvement and was not deployed. Endpoint correction is assessed separately below. Spatial masking does not verify vehicle matching between sensors.';host.append(p);
   }
   if(reconstruction.pair_diagnostics?.length){
    const h=document.createElement('h4');h.textContent=`Every ${corridor==='finch'?'Finch':'Florida'} pair · current recorded hour`;host.append(h);
    const table=document.createElement('table'),head=document.createElement('tr');
    for(const label of ['From → To','Direction','Departures','Arrivals','Displayed estimates','Final motion rejection']){const th=document.createElement('th');th.textContent=label;head.append(th);}table.append(head);
    for(const link of reconstruction.pair_diagnostics){const row=document.createElement('tr');for(const value of [link.names.join(' → '),link.direction,link.departure_candidates,link.arrival_candidates,link.displayed_matches,link.final_rejections]){const td=document.createElement('td');td.textContent=value;row.append(td);}table.append(row);}host.append(table);
    const note=document.createElement('p');note.textContent='Enable “Estimate between intersections” to show the supported dashed connections. These counts cover all sites and both directions for this hour; the plot follows your filters. Unmatched endpoints are fragments, not counts of missing unique vehicles. Turning exits, incomplete movements, ambiguous identity and motion conflicts remain unconnected.';host.append(note);
   }
   if(reconstruction.all_site_validation?.length){
    const h=document.createElement('h4');h.textContent='Local endpoint correction · site-by-site validation';host.append(h);
    for(const site of reconstruction.all_site_validation){const p=document.createElement('p');p.textContent=`${site.name}: ${site.methods.strict.accepted} → ${site.methods['noise_0.1'].accepted} of ${site.methods.strict.eligible} masked gaps accepted; new-case error ${site.new_cases.mae_m?.toFixed(2)??'unavailable'} m. ${site.correction_enabled?'Bounded correction enabled.':'Correction withheld: site error exceeds the quality threshold; strict estimator remains.'}`;host.append(p);}
   }
   const endpointStudy=reconstruction.endpoint_validation;
   if(endpointStudy){
    const h=document.createElement('h4');h.textContent='Endpoint-speed correction · untouched Florida hour';host.append(h);
    const intro=document.createElement('p');intro.textContent=`Test: November 13, 17:00–18:00 Florida time, excluding IDs seen in the earlier hour. Selected policy: ${endpointStudy.selected}.`;host.append(intro);
    for(const [name,row] of Object.entries(endpointStudy.test||{})){
     const p=document.createElement('p');p.textContent=`${name}: ${row.accepted}/${row.eligible} gaps accepted (${(100*row.coverage).toFixed(1)}%). Newly accepted: ${row.newly_accepted.n}, position error ${row.newly_accepted.mae_m?.toFixed(3)??'unavailable'} m. Previously accepted gaps lost: ${row.lost_strict_cases}.`;host.append(p);
     for(const [gap,g] of Object.entries(row.by_gap||{})){const t=document.createElement('p');t.textContent=`${gap}s: ${g.accepted}/${g.eligible} accepted; ${g.newly_accepted.n} additional gaps, new-case error ${g.newly_accepted.mae_m?.toFixed(3)??'unavailable'} m.`;host.append(t);}
    }
    const p=document.createElement('p');p.textContent=`Current displayed gaps with corrected endpoint speeds: ${reconstruction.endpoint_corrected_gaps??0}. Corrections apply only to inferred within-intersection curves with quiet visible samples. Recorded data and positions remain unchanged. Existing error bands do not cover these new cases. This does not validate identity matching between sensors.`;host.append(p);
   }
   const archive=reconstruction.archive_validation;
   if(archive){
    const h=document.createElement('h4');h.textContent='Additional Florida archives · longer gaps and blind matching';host.append(h);
    const info=document.createElement('p');info.textContent=`November 13: morning training/selection, afternoon held out. Selected shape: ${archive.selected_shape}; selected association: ${archive.selected_association}. These shape/association candidates were not deployed.`;host.append(info);
    for(const [method,row] of Object.entries(archive.results?.test||{})){
     const p=document.createElement('p');p.textContent=`${method}: ${row.accepted}/${row.eligible} accepted; ${row.common.n} common masks; mean position error ${row.common.mae_m?.toFixed(3)??'unavailable'} m.`;host.append(p);
     for(const [gap,m] of Object.entries(row.by_gap||{})){const line=document.createElement('p');line.textContent=`${gap}-second hidden interval: ${m.n} common masks, position error ${m.mae_m?.toFixed(3)??'unavailable'} m, speed error ${m.speed_mae_mps?.toFixed(3)??'unavailable'} m/s.`;host.append(line);}
    }
    for(const [scenario,methods] of Object.entries(archive.association_test||{}))for(const [method,m] of Object.entries(methods)){const p=document.createElement('p');p.textContent=`Identity-blind ${scenario} · ${method}: ${m.correct}/${m.eligible} correct matches; ${m.false} wrong matches; precision ${m.precision==null?'unavailable':(m.precision*100).toFixed(1)+'%'}.`;host.append(p);}
    const p=document.createElement('p');p.textContent='Same-sensor spatial masks are a proxy, not proof of identity or path accuracy between intersections. Archived signal state is unavailable for this comparison. These remain retrospective estimates.';host.append(p);
   }
   const association=reconstruction.association_validation;
   if(association){
    const heading=document.createElement('h4');heading.textContent='Tracklet matching · held-out spatial masks';host.append(heading);
    for(const [scenario,methods] of Object.entries(association.test||{}))for(const [method,m] of Object.entries(methods)){
     const p=document.createElement('p');p.textContent=`${scenario==='complete'?'All endpoints available':'Missing departures and arrivals'} · ${method}: ${m.correct}/${m.eligible} correct recovered matches (${m.recall==null?'unavailable':(100*m.recall).toFixed(1)+'%'}); ${m.false} wrong matches; precision ${m.precision==null?'unavailable':(100*m.precision).toFixed(1)+'%'}.`;host.append(p);
    }
    const p=document.createElement('p');p.textContent='This earlier global-method experiment recovered more matches but made more errors. Current displayed association policy: '+(reconstruction.association_method||'conservative matcher')+'. Same-sensor masks do not verify identities between intersections.';host.append(p);
   }
   for(const text of reconstruction.limitations||[]){const p=document.createElement('p');p.textContent=text;host.append(p);}
  }else host.textContent='No method has completed the required held-out comparison yet.';
  if(!aligned)el('layer-counts').textContent='Estimated layers unavailable for this window.';
  draw();
 }catch(e){reconstruction=null;el('reconstruction-status').textContent=e.message;for(const id of ['within-layer','between-layer'])el(id).disabled=true;draw();}
}
for(const id of ['within-layer','between-layer','color-layer'])if(el(id))el(id).onchange=draw;
refreshReconstruction();setInterval(refreshReconstruction,15000);
