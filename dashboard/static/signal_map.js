'use strict';
// Physical-location inventory and live phase identities are separate. No automatic join.
const signalDisplay={layouts:[],markers:new Map(),snapshots:new Map(),region:null,busy:false,layer:null};
const signalPrefixes={'OBC-AG-SA-C618861':'DR','OBC-AG-SA-C351163':'JA','OBC-AG-SA-C251055':'YG','OBC-AG-SA-C618857':'NO','OBC-AG-SA-C251071':'SI','OBC-AG-SA-C257220':'WE','OBC-AG-SA-C251064':'IS','OBC-AG-SA-C257238':'KI','OBC-AG-SA-C251052':'AL','OBC-AG-SA-C257208':'MG'};
let directionLayer=null,directionKey=null;
function renderDirectionGuide(){
  if(!map)return;
  if(!directionLayer)directionLayer=L.layerGroup().addTo(map);
  const site=state.site,origin=site?.reference_location;
  const key=(site?.id||'')+':'+(map.getZoom()>=17);
  if(key===directionKey)return;directionKey=key;directionLayer.clearLayers();
  const refs=[...signalDisplay.markers.values()].filter(m=>m.layout.site===site?.id);
  if($('direction-selection'))$('direction-selection').textContent=site?site.name+' · '+refs.map(m=>m.reference+' = '+m.slot).join('; '):'Select an intersection to see its marker IDs and compass guide.';
  if(!origin||map.getZoom()<17)return;
  for(const [east,north,label] of [[0,60,'N'],[60,0,'E'],[0,-60,'S'],[-60,0,'W']]){
    const point=[origin.lat+north/111320,origin.lng+east/(111320*Math.cos(origin.lat*Math.PI/180))];
    L.marker(point,{interactive:false,zIndexOffset:700,icon:L.divIcon({className:'direction-compass',html:`<span>${label}</span>`,iconSize:[24,24],iconAnchor:[12,12]})}).addTo(directionLayer);
  }
}
function signalOffsets(count){
  if(count===1)return [[0,0,'Centre']];
  if(count===4)return [[-18,18,'NW corner'],[18,18,'NE corner'],[18,-18,'SE corner'],[-18,-18,'SW corner']];
  return [[-12,0,'Location A — side unconfirmed'],[12,0,'Location B — side unconfirmed']];
}
function signalPreviewColour(snapshot,phase,receivedAt,now=Date.now()){
  if(!phase||!snapshot?.stream_receiving||now-receivedAt>5000)return 'UNKNOWN';
  const p=snapshot.phases.find(p=>p.phase===phase);
  return p&&['RED','YELLOW','GREEN'].includes(p.display_status)?p.display_status:'UNKNOWN';
}
function signalBinding(key){try{return localStorage.getItem('ouster-signal-preview:'+key)||'';}catch{return '';}}
function signalIcon(colour,phase,reference){
  return L.divIcon({className:'physical-signal',iconSize:[24,54],iconAnchor:[12,27],html:`<div class="signal-lamps" aria-label="${escapeHTML(reference)} · ${escapeHTML(phase?'Manual preview phase '+phase+': '+colour:'Phase unassigned')}">${['RED','YELLOW','GREEN'].map(c=>`<i class="lamp ${c.toLowerCase()} ${c===colour?'lit':''}"></i>`).join('')}</div><span class="signal-caption">${escapeHTML(reference)}<br>${phase?'P'+escapeHTML(phase)+'*':'?'}</span>`});
}
function signalPopup(item){
  const div=document.createElement('div');
  const title=document.createElement('strong');title.textContent=item.reference+' · '+item.layout.name+' · '+item.slot;
  const note=document.createElement('p');note.textContent='Approximate layout from your description. Marker coordinates are schematic, not surveyed. '+(item.layout.reference_check||'');
  const detail=document.createElement('p');detail.textContent='Phase Details is unavailable; phase_id ↔ phaseNumber and movement-to-head mapping are unverified. Select a phase only to preview its received state here. This does not verify the assignment.';
  const label=document.createElement('label');label.textContent='Manual real-time phase preview';
  const select=document.createElement('select');select.setAttribute('aria-label','Manual real-time phase preview');select.add(new Option('Unassigned — no colour',''));
  const entry=signalDisplay.snapshots.get(item.layout.site);
  const phases=(entry?.data.phases||[]).filter(p=>['RED','YELLOW','GREEN'].includes(p.status));
  phases.forEach(p=>select.add(new Option('Phase '+p.phase+' · last report '+p.status,p.phase)));
  const prior=signalBinding(item.key);
  if(prior&&!phases.some(p=>p.phase===prior))select.add(new Option('Phase '+prior+' · unavailable',prior));
  select.value=prior;
  select.onchange=()=>{try{localStorage.setItem('ouster-signal-preview:'+item.key,select.value);}catch{toast('Browser could not save your phase selection.');}paintSignalMarkers();};
  label.append(select);div.append(title,note,detail,label);return div;
}
function rebuildSignalMarkers(){
  if(!map)return;
  if(!signalDisplay.layer)signalDisplay.layer=L.layerGroup().addTo(map);
  signalDisplay.layer.clearLayers();signalDisplay.markers.clear();signalDisplay.snapshots.clear();
  signalDisplay.region=$('region').value;
  for(const layout of signalDisplay.layouts){
    const site=state.sites.find(s=>s.id===layout.site&&s.region===signalDisplay.region);
    const origin=site?.reference_location;if(!origin)continue;
    signalOffsets(layout.reported_locations).forEach(([east,north,slot],i)=>{
      const point=[origin.lat+north/111320,origin.lng+east/(111320*Math.cos(origin.lat*Math.PI/180))];
      const key=layout.site+':'+i,item={key,layout,slot,reference:signalPrefixes[layout.site]+(i+1)};
      item.marker=L.marker(point,{icon:signalIcon('UNKNOWN',signalBinding(key),item.reference),zIndexOffset:600});
      item.marker.bindTooltip(`${item.reference} · ${layout.name} · ${slot} · approximate; phase assignment unverified`);
      item.marker.bindPopup(()=>signalPopup(item),{maxWidth:330});
      signalDisplay.markers.set(key,item);
    });
  }
  directionKey=null;
  paintSignalMarkers();
}
function paintSignalMarkers(){
  if(!signalDisplay.layer)return;
  renderDirectionGuide();
  const visible=$('show-signal-layout')?.checked&&map.getZoom()>=17;
  for(const item of signalDisplay.markers.values()){
    const entry=signalDisplay.snapshots.get(item.layout.site),phase=signalBinding(item.key);
    item.marker.setIcon(signalIcon(signalPreviewColour(entry?.data,phase,entry?.at||0),phase,item.reference));
    if(visible&&!signalDisplay.layer.hasLayer(item.marker))signalDisplay.layer.addLayer(item.marker);
    if(!visible&&signalDisplay.layer.hasLayer(item.marker))signalDisplay.layer.removeLayer(item.marker);
  }
}
async function updateSignalMap(){
  if(!map||!state.sites.length||!signalDisplay.layouts.length)return;
  if(signalDisplay.region!==$('region').value)rebuildSignalMarkers();
  paintSignalMarkers();
  if(signalDisplay.busy||state.tab!=='live'||!$('show-signal-layout').checked)return;
  const region=signalDisplay.region;signalDisplay.busy=true;
  try{
    const result=await api('/api/network-signals?region='+encodeURIComponent(region));
    if(region!==$('region').value)return;
    result.snapshots.forEach(data=>signalDisplay.snapshots.set(data.site,{data,at:Date.now()}));
    paintSignalMarkers();
  }catch{signalDisplay.snapshots.clear();paintSignalMarkers();}
  finally{signalDisplay.busy=false;}
}
action(async()=>{
  const result=await api('/api/signal-layouts');signalDisplay.layouts=result.sites;
  const controls=document.createElement('div');controls.className='panel filters';
  controls.innerHTML='<label><input id="show-signal-layout" type="checkbox" checked> Show reported signal locations (zoom 17+)</label><span class="subtle">Approximate layout · ? = unassigned · P#* = manual phase preview, unverified movement mapping. Click a signal to select a received phase.</span>';
  document.querySelector('.network-grid').before(controls);
  const guide=document.createElement('article');guide.className='panel padded';guide.id='signal-direction-guide';
  guide.innerHTML='<h3>Signal location and movement reference</h3><p id="direction-selection"></p><p>The map is north-up: N at the top, E right, S bottom, W left. Compass letters indicate geographic directions, not verified road approaches. NW/NE/SE/SW identify corners around the intersection reference.</p><p>Movement codes describe where traffic comes from and goes to: <strong>NS = north → south; SN = south → north; EW = east → west; WE = west → east.</strong> A marker’s physical corner does not determine which movement it controls.</p><p>Reply with: <code>marker ID; actual position; controlled movement(s); real-time phase number if known</code>. Multiple movements on one assembly can be listed separately.</p>';
  document.querySelector('.network-grid').after(guide);
  $('show-signal-layout').onchange=paintSignalMarkers;
  const timer=setInterval(()=>{if(map){map.on('zoomend',paintSignalMarkers);clearInterval(timer);updateSignalMap();}},200);
  setInterval(updateSignalMap,1000);
});
