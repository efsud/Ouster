'use strict';
const $ = id => document.getElementById(id);
const state = {sites:[],corridors:[],metrics:{},site:null,metric:'control_delay',rows:[],tab:'live'};
const titles = {live:'Live network',history:'Historical performance',ctm:'CTM explorer',optimization:'Optimization',guide:'Methods & learning',anomalies:'Anomalies'};
const escapeHTML = value => String(value).replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const number = v => v===null || v===undefined ? '—' : Number(v).toLocaleString(undefined,{maximumFractionDigits:1});
let map, sitesLayer, objectLayer, toastTimer, liveRequest=0;
const displayedFrames=new Map(),sensorMarkers=new Map(),movingObjects=new Map();
let liveBusy=false;
function clearObjects(){objectLayer?.clearLayers();movingObjects.clear();}
function animateObjects(now){
  for(const [key,m] of movingObjects){
    if(Date.now()>m.expires||state.tab!=='live'||map.getZoom()<17){objectLayer.removeLayer(m.marker);movingObjects.delete(key);continue;}
    const fraction=Math.min(1,(now-m.started)/250);
    m.marker.setLatLng([m.from.lat+(m.to[0]-m.from.lat)*fraction,m.from.lng+(m.to[1]-m.from.lng)*fraction]);
  }
  requestAnimationFrame(animateObjects);
}
requestAnimationFrame(animateObjects);
function toast(message){$('toast').textContent=message;$('toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').hidden=true,9000);}
async function api(path, data){
  const response=await fetch(path,data===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
  const result=await response.json();if(!response.ok)throw new Error(result.error||'Request failed');return result;
}
async function action(fn){try{await fn();}catch(e){toast(e.message);}}
document.querySelectorAll('[data-tab]').forEach(button=>button.addEventListener('click',()=>{
  state.tab=button.dataset.tab;
  document.querySelectorAll('.page').forEach(p=>p.hidden=p.id!==state.tab);
  document.querySelectorAll('.nav').forEach(b=>b.classList.toggle('active',b===button));
  $('page-title').textContent=titles[state.tab];
  if(state.tab==='live')setTimeout(()=>{map?.invalidateSize();action(refreshLive);},0);
  if(state.tab==='ctm'&&!$('heatmap').children.length)action(runCTM);
  if(state.tab==='anomalies')action(()=>loadAnomalies());
}));
function initMap(){
  if(!window.L){$('map').innerHTML='<div class="empty">Map library is unavailable. Run the vendor setup in README.md.</div>';return;}
  map=L.map('map').setView([43.751,-79.542],13);
  let tileErrorShown=false;
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:20,attribution:'© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'}).on('tileerror',()=>{if(!tileErrorShown){$('map-note').textContent='Basemap unavailable; check network';tileErrorShown=true;}}).addTo(map);
  sitesLayer=L.layerGroup().addTo(map);objectLayer=L.layerGroup().addTo(map);
  map.on('moveend',()=>action(refreshLive));
}
function renderNetwork(){
  const region=$('region').value;
  $('global-notice').textContent=region==='Florida'?'Florida · SR-436 corridor, Altamonte Springs · Seven intersections selected. Live data awaits API access and sensor calibration.':'Toronto · Finch West LRT corridor · Ten sensors · approximate live animation. Positions and rotation are uncalibrated; receipt freshness does not establish sensor latency.';
  const list=state.sites.filter(s=>s.region===region);
  state.site=null;clearObjects();sitesLayer?.clearLayers();sensorMarkers.clear();
  $('site-count').textContent=list.length;$('inventory-count').textContent=list.length;
  $('mapped-count').textContent=list.filter(s=>s.calibration_status?.valid||s.reference_location).length;
  $('region-label').textContent=region==='Florida'?'SR-436 · Altamonte Springs':'Finch West LRT · Toronto';
  $('object-count').textContent='—';$('frame-status').textContent='Waiting for a live stream';
  $('selected-name').textContent='Choose an intersection';$('selected-detail').textContent='Verified sensor origins and read-only stream access are needed before live objects can appear.';
  $('site-state').textContent='Awaiting access';$('connection').textContent='Not connected';
  if(map)map.setView(region==='Florida'?[28.661,-81.386]:[43.751,-79.542],13,{animate:false});
  $('sites-list').replaceChildren();
  if(!list.length)$('sites-list').innerHTML='<div class="empty"><strong>No sites configured.</strong>Use the Python launcher to enter API credentials, then add verified Toronto site IDs and sensor origins. No sites have been inferred.</div>';
  for(const site of list){
    const button=document.createElement('button');button.className='site';button.dataset.siteId=site.id;
    button.innerHTML=`<strong>${escapeHTML(site.name)}</strong><small>${escapeHTML(site.id)}</small><span class="status">${site.calibration_status?.valid?'Location verified':'Location / access pending'}</span>`;
    button.onclick=()=>selectSite(site,button);$('sites-list').append(button);
    if((site.calibration_status?.valid||site.reference_location)&&map){
      const location=site.calibration_status?.valid?site.origin:site.reference_location;
      const point=[location.lat,location.lng];
      const label=document.createElement('span');label.textContent=site.name+' · '+site.id+(site.calibration_status?.valid?' · calibrated sensor':' · approximate intersection, mounting point unverified');
      sensorMarkers.set(site.id,L.circleMarker(point,{radius:7,color:'#fff',weight:3,dashArray:site.calibration_status?.valid?null:'3 3',fillColor:'#197d79',fillOpacity:1}).bindTooltip(label).on('click',()=>selectSite(site,button)).addTo(sitesLayer));
    }
  }
  const referencePoints=list.map(s=>s.calibration_status?.valid?s.origin:s.reference_location).filter(Boolean);
  if(map&&referencePoints.length)map.fitBounds(referencePoints.map(p=>[p.lat,p.lng]),{padding:[35,35],maxZoom:14,animate:false});
  const paths=state.corridors.filter(c=>c.region===region);
  for(const corridor of paths){
    if(!map)break;
    const label=document.createElement('span');label.textContent=corridor.name+' · verified corridor';
    L.polyline(corridor.coordinates.map(([lng,lat])=>[lat,lng]),{color:'#197d79',weight:4,opacity:.6}).bindTooltip(label).addTo(sitesLayer);
  }
  $('map-note').textContent=paths.length?paths.length+' verified corridor paths':referencePoints.length+' approximate intersection markers; sensor origins unverified';
  action(refreshLive);
}
function selectSite(site,button){
  state.site=site;document.querySelectorAll('.site').forEach(b=>b.classList.toggle('selected',b===button));
  $('selected-name').textContent=site.name;$('selected-detail').textContent=`${site.id} · ${site.corridor||site.region} · ${site.timezone||'Timezone pending'}`;
  const location=site.calibration_status?.valid?site.origin:site.reference_location;
  if(location)map?.setView([location.lat,location.lng],18);
  action(refreshLive);
}
async function refreshLive(){
  if(state.tab!=='live'||liveBusy)return;
  const region=$('region').value,request=++liveRequest;
  liveBusy=true;let result;
  try{result=await api('/api/network-live?region='+encodeURIComponent(region)+'&approximate='+$('approximate-objects').checked+'&rotation='+$('preview-rotation').value);}finally{liveBusy=false;}
  if(request!==liveRequest||$('region').value!==region||state.tab!=='live')return;
  const seen=new Set();
  const fresh=result.snapshots.filter(s=>['live','approximate'].includes(s.state));
  $('health-rows').innerHTML=result.snapshots.map(s=>`<tr><td>${escapeHTML(s.site)}</td><td>${escapeHTML(s.health?.state||'not_started')}</td><td>${utcTime(s.health?.last_receipt)}</td><td>${utcTime(s.health?.last_sensor_time)}</td><td>${s.health?.saved_count||0}</td><td>${escapeHTML(s.health?.error||s.calibration?.reasons?.join('; ')||s.state)}</td></tr>`).join('');
  const receiving=result.snapshots.filter(s=>s.health?.last_receipt&&Date.now()/1000-s.health.last_receipt<5).length;
  $('connection').textContent=receiving?`${receiving} / ${result.snapshots.length} receiving · ${fresh.length} object streams`:fresh.length?`${fresh.length} / ${result.snapshots.length} sites live`:'No verified live stream';
  let visible=0;
  for(const data of result.snapshots){
    sensorMarkers.get(data.site)?.setStyle({fillColor:data.active_anomalies?'#bf643c':data.state==='live'?'#197d79':'#87949b'});
    const button=Array.from(document.querySelectorAll('.site')).find(b=>b.dataset.siteId===data.site);
    if(button)button.querySelector('.status').textContent=data.health?.error||data.state;
    if(state.site?.id===data.site){
      $('site-state').textContent=data.state;
      $('selected-detail').textContent=data.reason||`${data.site} · ${data.objects.length} objects · ${data.rejected_objects||0} invalid objects excluded`;
    }
    const beforeVisible=visible;
    if(map&&map.getZoom()>=17&&['live','approximate'].includes(data.state))for(const o of data.objects){
      if(!map.getBounds().contains([o.lat,o.lng]))continue;
      visible++;
      const key=data.site+':'+(data.session||'')+':'+o.id;seen.add(key);
      let m=movingObjects.get(key);
      const target=[o.lat,o.lng];
      if(!m){
        const marker=L.circleMarker(target,{radius:5,color:o.kind==='cyclist'?'#a46eab':o.kind==='vehicle'?'#426fba':'#17a990',weight:2,fillOpacity:.9}).addTo(objectLayer);
        m={marker,from:marker.getLatLng(),to:target,started:performance.now()};movingObjects.set(key,m);
      }
      if(m.event!==data.event_key||m.to[0]!==o.lat||m.to[1]!==o.lng){m.from=m.marker.getLatLng();m.to=target;m.started=performance.now();m.event=data.event_key;}
      m.expires=Date.now()+Math.max(0,5-(data.age_s||0))*1000;
      const label=document.createElement('span');label.textContent=`${data.site} · ${o.kind||o.class} ${o.id} · ${data.state==='approximate'?'APPROXIMATE · receipt time':'sensor time'} ${utcTime(o.timestamp)} · age ${number(o.age_s)} s`;
      m.marker.bindTooltip(label);

    }
    if(visible>beforeVisible&&data.event_key&&displayedFrames.get(data.site)!==data.event_key){
      displayedFrames.set(data.site,data.event_key);requestAnimationFrame(()=>api('/api/latency',{event_key:data.event_key,displayed_at:Date.now()/1000}).catch(()=>{}));
    }
  }
  for(const [key,m] of movingObjects)if(!seen.has(key)){objectLayer.removeLayer(m.marker);movingObjects.delete(key);}
  $('object-count').textContent=fresh.length?visible:'—';
  $('frame-status').textContent=fresh.length?(map?.getZoom()<17?'Zoom to 17+ to view objects':`${fresh.length} fresh site streams`):'Waiting for a live stream';
}
function filters(){
  const q=new URLSearchParams({cadence:$('cadence').value});
  if($('history-site').value)q.set('site',$('history-site').value);
  if($('approach').value)q.set('approach',$('approach').value);
  for(const [id,key] of [['from','start'],['to','end']])if($(id).value)q.set(key,String(new Date($(id).value).getTime()/1000));
  if(q.has('start')&&q.has('end')&&Number(q.get('start'))>=Number(q.get('end')))throw new Error('End must follow start');
  return q;
}
function renderCards(){
  $('kpi-cards').replaceChildren();
  for(const [key,[name,unit]] of Object.entries(state.metrics)){
    // Latest window per selected approach. Never average incompatible rates/quantiles.
    const approaches=new Set(state.rows.map(r=>r.approach));
    const latest=state.rows.at(-1);
    const value=approaches.size<=1?latest?.values[key]:null;
    const b=document.createElement('button');b.className='kpi-card'+(state.metric===key?' active':'');
    b.innerHTML=`<span>${escapeHTML(name)}</span><strong>${number(value)} <small>${escapeHTML(unit)}</small></strong><small>${approaches.size>1?'Select one approach':latest?'Latest saved window':'Awaiting observations'}</small>`;
    b.onclick=()=>{state.metric=key;renderCards();renderChart();};$('kpi-cards').append(b);
  }
}
function lineChart(rows,key){
  if(!rows.length)return '<div class="empty"><strong>No saved observations in this range.</strong>Collect or import data, or load the labelled learning dataset.</div>';
  const points=rows.filter(r=>r.values[key]!==null);
  if(!points.length)return '<div class="empty"><strong>This KPI is unavailable.</strong>Its required observations or synchronized signal metadata are missing.</div>';
  const W=950,H=255,L=62,R=20,T=20,B=45;
  const minT=Math.min(...rows.map(r=>r.start)),maxT=Math.max(...rows.map(r=>r.end));
  let low=Math.min(0,...points.map(r=>r.values[key])),high=Math.max(1,...points.map(r=>r.values[key]))*1.12;
  const x=t=>L+(t-minT)/(maxT-minT||1)*(W-L-R),y=v=>T+(high-v)/(high-low)*(H-T-B);
  let svg=`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${escapeHTML(state.metrics[key][0])} by reporting window in UTC">`;
  for(let i=0;i<5;i++){const value=low+(high-low)*i/4,py=y(value);svg+=`<line x1="${L}" x2="${W-R}" y1="${py}" y2="${py}" stroke="#e5edeb"/><text x="${L-10}" y="${py+4}" text-anchor="end" fill="#83928d" font-size="10">${number(value)}</text>`;}
  const colors=['#197d79','#5677ba','#b2813f','#915e9d'];
  [...new Set(rows.map(r=>r.approach))].forEach((approach,index)=>{
    const color=colors[index%colors.length];let last=null;
    for(const r of rows.filter(r=>r.approach===approach)){
      if(r.values[key]===null){last=null;continue;}
      const cx=x(r.start),cy=y(r.values[key]);
      if(last&&last.end===r.start)svg+=`<line x1="${last.x}" y1="${last.y}" x2="${cx}" y2="${cy}" stroke="${color}" stroke-width="2"/>`;
      svg+=`<circle cx="${cx}" cy="${cy}" r="3" fill="${color}"><title>${escapeHTML(approach)} · ${new Date(r.start*1000).toISOString()} · ${number(r.values[key])} ${escapeHTML(state.metrics[key][1])} · ${escapeHTML(r.quality.status)}</title></circle>`;
      last={x:cx,y:cy,end:r.end};
    }
  });
  for(let i=0;i<5;i++){const t=minT+(maxT-minT)*i/4;svg+=`<text x="${x(t)}" y="${H-15}" text-anchor="middle" fill="#83928d" font-size="10">${new Date(t*1000).toISOString().slice(11,16)}</text>`;}
  return svg+'</svg>';
}
function renderChart(){
  $('chart-title').textContent=state.metrics[state.metric][0]+' · '+state.metrics[state.metric][1];
  $('history-chart').innerHTML=lineChart(state.rows,state.metric);
}
async function loadHistory(resetApproaches=false){
  if(!$('history-site').value){state.rows=[];renderCards();renderChart();return;}
  const query=filters();query.set('paged','true');query.set('limit','1000');
  const response=await api('/api/history?'+query);const rows=response.items;state.rows=rows;historyOffset=response.next_offset;
  $('history-next').hidden=historyOffset===null;
  if(resetApproaches){
    $('approach').replaceChildren(new Option('All approaches',''));
    [...new Set(rows.map(r=>r.approach))].forEach(a=>$('approach').add(new Option(a,a)));
  }
  const synthetic=$('history-site').value==='DEMO-001';
  $('history-source').textContent=synthetic?'SYNTHETIC LEARNING DATA · Generated examples, not Toronto or Florida measurements. Fixed date: '+(rows[0]?new Date(rows[0].start*1000).toISOString().slice(0,10):'outside selected range'):'Annotated imports · Input quality checks are not a substitute for independent field validation.';
  $('window-count').textContent=rows.length+' windows';renderCards();renderChart();
  $('quality-rows').innerHTML=rows.map(r=>`<tr><td>${new Date(r.start*1000).toISOString().replace('T',' ').slice(0,19)}</td><td>${escapeHTML(r.approach)}</td><td>${r.quality.valid_tracks}</td><td>${number(r.quality.coverage*100)}%</td><td>${escapeHTML(r.quality.flags.length?r.quality.flags.join('; '):'Passes input checks · field validation pending')}</td></tr>`).join('');
  bindEvidence();await loadAvailability();
}
async function runCTM(){
  const p=new URLSearchParams({demand:$('demand').value,green:$('green').value,offset:$('offset').value,intersections:$('ctm-scale').value});
  const result=await api('/api/ctm?'+p);
  const W=840,H=290,L=40,T=10,B=30,cols=result.history.length,rows=result.history[0].density.length;
  const cw=(W-L)/cols,ch=(H-T-B)/rows;
  let svg=`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="CTM density over distance and time">`;
  result.history.forEach((h,c)=>h.density.forEach((density,r)=>{
    const ratio=density/result.jam_density;
    const color=ratio<.5?`hsl(${155-ratio*100} 32% ${94-ratio*100}%)`:`hsl(${55-(ratio-.5)*100} 47% 53%)`;
    svg+=`<rect x="${L+c*cw}" y="${T+r*ch}" width="${cw+.2}" height="${ch+.2}" fill="${color}"><title>${h.time} s · Cell ${r+1} · ${density} veh/km</title></rect>`;
  }));
  for(let r=0;r<=rows;r+=6){const y=T+r*ch;svg+=`<line x1="${L}" x2="${W}" y1="${y}" y2="${y}" stroke="#fff" stroke-width="2"/><text x="${L-7}" y="${Math.min(y+4,H-B)}" text-anchor="end" fill="#798d87" font-size="10">${r*50}m</text>`;}
  for(let i=0;i<=3;i++)svg+=`<text x="${L+(W-L)*i/3}" y="${H-6}" text-anchor="${i===3?'end':i===0?'start':'middle'}" fill="#798d87" font-size="11">${i*5} min</text>`;
  $('heatmap').innerHTML=svg+'</svg>';
  $('ctm-stats').innerHTML=[['VEHICLES EXITED',number(result.departed),'Fractional macroscopic vehicles'],['UPSTREAM WAITING',number(result.backlog),'Unserved demand retained'],['EXCESS VEHICLE-HOURS',number(result.excess_vehicle_hours),'Model estimate over 15 minutes'],['CONSERVATION ERROR',result.conservation_error.toExponential(1),'Entered − exited − remaining']].map(([a,b,c])=>`<article><span>${a}</span><strong>${b}</strong><small>${c}</small></article>`).join('');
}
const methods=[['Control delay','Mean of (arrival − entry − approach length / free-flow speed). Requires complete traversals.'],['Stopped delay','Time-integral of speed at or below the crawl threshold. Requires a complete observed traversal and valid samples.'],['Queue length · P95','95th percentile of visible queue extents on a regular time grid. Membership requires lane, spacing, and queue-region checks.'],['Arrivals on green','100 × green arrivals / all arrivals. Requires verified clock synchronization and a known signal state for every arrival.'],['Split failure','100 × complete visible cycles with a residual queue / complete visible cycles.'],['Approach volume','Unique physical trajectory entries × 3600 / window seconds. Entry events may be used without a complete traversal.'],['Discharge rate','Queued departures during effective green × 3600 / green seconds / lane count.'],['CTM vs observed KPIs','CTM propagates aggregate density. It does not directly observe individual stopped time, arrivals, or LiDAR queue geometry. Simulation outputs remain separate.']];
$('methods').innerHTML=methods.map(([title,body])=>`<article class="panel padded"><h3>${title}</h3><p>${body}</p></article>`).join('');
$('region').onchange=renderNetwork;
for(const id of ['approximate-objects','preview-rotation'])$(id).onchange=()=>{liveRequest++;clearObjects();action(refreshLive);};
$('cadence').onchange=()=>action(()=>loadHistory(true));
$('apply-filter').onclick=()=>action(()=>loadHistory());
$('history-site').onchange=()=>{ $('approach').value='';action(()=>loadHistory(true));};
$('export').onclick=()=>action(async()=>{if(!$('history-site').value)throw new Error('Select a dataset');window.location.href='/api/export.csv?'+filters();});
$('load-demo').onclick=()=>action(async()=>{
  await api('/api/demo',{});
  if(!Array.from($('history-site').options).some(o=>o.value==='DEMO-001'))$('history-site').add(new Option('Learning dataset · SYNTHETIC','DEMO-001'));
  $('history-site').value='DEMO-001';$('from').value='';$('to').value='';$('approach').value='';await loadHistory(true);toast('36 synthetic windows saved. No BlueCity data was used.');
});
$('import-file').onchange=()=>action(async()=>{
  const file=$('import-file').files[0];if(!file)return;
  if(file.size>5_000_000)throw new Error('Import limit is 5 MB');
  const data=JSON.parse(await file.text());const result=await api('/api/import',data);toast(result.saved+' annotated windows saved');await loadHistory();$('import-file').value='';
});
$('collect').onclick=()=>action(async()=>{
  if(!$('history-site').value||$('history-site').value==='DEMO-001')throw new Error('Select a real configured site');
  const payload={site:$('history-site').value,kind:$('collect-kind').value};
  if(payload.kind==='turning_counts'){
    if(!$('from').value||!$('to').value)throw new Error('Choose a start and end time');
    payload.start=new Date($('from').value).toISOString();payload.end=new Date($('to').value).toISOString();
  }
  $('collect').disabled=true;
  try{const result=await api('/api/collect',payload);toast(result.saved+' · '+result.note);}finally{$('collect').disabled=false;}
});
for(const [id,unit] of [['demand','veh/h'],['green','s'],['offset','s']])$(id).oninput=()=>$(id+'-out').textContent=$(id).value+' '+unit;
$('run-ctm').onclick=()=>action(runCTM);
action(async()=>{
  const status=await api('/api/status');state.sites=status.sites;state.corridors=status.corridors||[];state.metrics=status.metrics;
  initMap();renderNetwork();renderCards();renderChart();
  const requestedSite=new URLSearchParams(location.search).get('site');
  const requestedButton=Array.from(document.querySelectorAll('.site')).find(b=>b.dataset.siteId===requestedSite);
  requestedButton?.click();
  state.sites.sort((a,b)=>(a.region==='Toronto'?0:1)-(b.region==='Toronto'?0:1));
  state.sites.forEach(s=>{$('history-site').add(new Option(s.name,s.id));$('anomaly-site').add(new Option(s.name,s.id));});
  $('history-site').add(new Option('Learning dataset · SYNTHETIC','DEMO-001'));
  $('history-site').value=state.sites.find(s=>s.region==='Toronto')?.id||'';action(()=>loadHistory(true));
  setInterval(()=>refreshLive().catch(()=>{clearObjects();$('connection').textContent='Connection lost';$('object-count').textContent='—';}),250);
});

let historyOffset=null,rawCursor=null,anomalyOffset=null;
function utcTime(value){return typeof value==='number'?new Date(value*1000).toISOString().replace('T',' ').replace('Z',' UTC'):'—';}
async function loadAvailability(){
  const site=$('history-site').value;
  if(!site||site==='DEMO-001'){$('availability').textContent='Synthetic examples are separate from received observations.';return;}
  const a=await api('/api/availability?site='+encodeURIComponent(site));
  $('availability').textContent=`${a.count} raw events retained · sensor times ${utcTime(a.first)} to ${utcTime(a.last)} · last receipt ${utcTime(a.last_receipt)} · ${JSON.stringify(a.status_counts)}`;
}
function bindEvidence(){
  Array.from($('quality-rows').rows).forEach((tr,i)=>{
    tr.tabIndex=0;tr.title='Inspect calculation inputs and provenance';
    const show=()=>action(async()=>{const r=state.rows[i];const q=new URLSearchParams({site:r.site,approach:r.approach,start:r.start,end:r.end,source:r.source});$('window-evidence').textContent=JSON.stringify(await api('/api/window?'+q),null,2);});
    tr.onclick=show;tr.onkeydown=e=>{if(e.key==='Enter')show();};
  });
}
$('history-next').onclick=()=>action(async()=>{
  const q=filters();q.set('paged','true');q.set('offset',historyOffset);q.set('limit',1000);
  const page=await api('/api/history?'+q);state.rows.push(...page.items);historyOffset=page.next_offset;$('history-next').hidden=historyOffset===null;
  $('window-count').textContent=state.rows.length+' windows loaded';renderCards();renderChart();
  $('quality-rows').innerHTML=state.rows.map(r=>`<tr><td>${utcTime(r.start)}</td><td>${escapeHTML(r.approach)}</td><td>${r.quality.valid_tracks}</td><td>${number(r.quality.coverage*100)}%</td><td>${escapeHTML(r.quality.flags.join('; ')||'Passes input checks · field validation pending')}</td></tr>`).join('');bindEvidence();
});
async function inspectRaw(next=false){
  const site=$('history-site').value;if(!site||site==='DEMO-001')throw new Error('Select a real sensor');
  const q=filters();q.set('limit','20');q.set('cursor',next?rawCursor:0);
  const result=await api('/api/received?'+q);rawCursor=result.next_cursor;
  $('raw-data').textContent=JSON.stringify(result.items,null,2);$('raw-next').hidden=rawCursor===null;
}
$('inspect-raw').onclick=()=>action(()=>inspectRaw());$('raw-next').onclick=()=>action(()=>inspectRaw(true));
$('process-windows').onclick=()=>action(async()=>{
  const q=filters();if(!q.has('start')||!q.has('end'))throw new Error('Choose a five-minute-aligned date range first');
  const result=await api('/api/process',{site:$('history-site').value,start:Number(q.get('start')),end:Number(q.get('end')),cadence:'five_minute'});
  toast(result.saved+' calculated windows saved');await loadHistory(true);
});
$('process-daily').onclick=()=>action(async()=>{
  if(!$('process-day').value)throw new Error('Choose a Toronto calendar day');
  const result=await api('/api/process',{site:$('history-site').value,day:$('process-day').value,cadence:'daily'});
  toast(result.saved+' daily summaries saved');await loadHistory(true);
});
async function loadAnomalies(next=false){
  const q=new URLSearchParams({site:$('anomaly-site').value,category:$('anomaly-category').value,offset:next?anomalyOffset:0});
  const result=await api('/api/anomalies?'+q);anomalyOffset=result.next_offset;$('anomaly-next').hidden=anomalyOffset===null;
  if(!next)$('anomaly-list').replaceChildren();
  if(!result.items.length&&!next)$('anomaly-list').innerHTML='<div class="empty">No detected events. This does not establish normal traffic when reception or baselines are missing.</div>';
  for(const event of result.items){
    const panel=document.createElement('article');panel.className='anomaly-event';
    panel.innerHTML=`<h3>${escapeHTML(event.rule)} <span class="pill">${escapeHTML(event.category)} · ${escapeHTML(event.state)}</span></h3><p>${escapeHTML(event.site)} / ${escapeHTML(event.approach||'sensor')} · ${utcTime(event.start)} → ${utcTime(event.end)}</p><p>Severity: ${escapeHTML(event.severity)} · ${event.acknowledged_at?'Acknowledged '+utcTime(event.acknowledged_at):'Not acknowledged'}</p>`;
    const detail=document.createElement('details');const summary=document.createElement('summary');summary.textContent='Observed values, expected range and quality evidence';const pre=document.createElement('pre');pre.textContent=JSON.stringify(event.evidence,null,2);detail.append(summary,pre);panel.append(detail);
    if(event.category==='traffic'){
      const link=document.createElement('button');link.className='secondary';link.textContent='Open related history';link.onclick=()=>action(async()=>{
        $('history-site').value=event.site;$('from').value='';$('to').value='';$('approach').value='';
        document.querySelector('[data-tab=history]').click();await loadHistory(true);$('approach').value=event.approach;await loadHistory();
        const e=event.evidence;const q=new URLSearchParams({site:event.site,approach:event.approach,start:e.window_start,end:e.window_end,source:e.source});
        $('window-evidence').textContent=JSON.stringify(await api('/api/window?'+q),null,2);
      });panel.append(link);
    }
    const note=document.createElement('textarea');note.maxLength=2000;note.placeholder='Review note';note.setAttribute('aria-label','Review note for '+event.rule);note.value=event.note||'';
    const acknowledge=document.createElement('button');acknowledge.className='secondary';acknowledge.textContent='Acknowledge / save note';acknowledge.onclick=()=>action(async()=>{await api('/api/anomalies/acknowledge',{id:event.id,note:note.value});await loadAnomalies();});
    panel.append(note,acknowledge);$('anomaly-list').append(panel);
  }
  const evaluations=await api('/api/anomaly-evaluations?site='+encodeURIComponent($('anomaly-site').value));
  const counts={};evaluations.forEach(e=>counts[e.status]=(counts[e.status]||0)+1);
  $('anomaly-readiness').textContent=evaluations.length?Object.entries(counts).map(([k,v])=>k+': '+v).join(' · '):'No eligible KPI windows evaluated yet. Check reception, verified geometry and historical processing.';
}
$('anomaly-refresh').onclick=()=>action(()=>loadAnomalies());$('anomaly-next').onclick=()=>action(()=>loadAnomalies(true));
$('anomaly-site').onchange=()=>action(()=>loadAnomalies());$('anomaly-category').onchange=()=>action(()=>loadAnomalies());
$('anomaly-evaluate').onclick=()=>action(async()=>{await api('/api/anomalies/evaluate',{site:$('anomaly-site').value});await loadAnomalies();toast('Evaluation complete. Detections remain provisional.');});
