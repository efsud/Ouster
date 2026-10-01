'use strict';
// Physical-location inventory and live phase identities are separate. No automatic join.
const signalDisplay={layouts:[],markers:new Map(),snapshots:new Map(),region:null,busy:false,layer:null};
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
function signalIcon(colour,phase){
  return L.divIcon({className:'physical-signal',iconSize:[24,54],iconAnchor:[12,27],html:`<div class="signal-lamps" aria-label="${escapeHTML(phase?'Manual preview phase '+phase+': '+colour:'Phase unassigned')}">${['RED','YELLOW','GREEN'].map(c=>`<i class="lamp ${c.toLowerCase()} ${c===colour?'lit':''}"></i>`).join('')}</div><span class="signal-caption">${phase?'P'+escapeHTML(phase)+'*':'?'}</span>`});
}
function signalPopup(item){
  const div=document.createElement('div');
  const title=document.createElement('strong');title.textContent=item.layout.name+' · '+item.slot;
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
      const key=layout.site+':'+i,item={key,layout,slot};
      item.marker=L.marker(point,{icon:signalIcon('UNKNOWN',signalBinding(key)),zIndexOffset:600});
      item.marker.bindTooltip(`${layout.name} · ${slot} · approximate; phase assignment unverified`);
      item.marker.bindPopup(()=>signalPopup(item),{maxWidth:330});
      signalDisplay.markers.set(key,item);
    });
  }
  paintSignalMarkers();
}
function paintSignalMarkers(){
  if(!signalDisplay.layer)return;
  const visible=$('show-signal-layout')?.checked&&map.getZoom()>=17;
  for(const item of signalDisplay.markers.values()){
    const entry=signalDisplay.snapshots.get(item.layout.site),phase=signalBinding(item.key);
    item.marker.setIcon(signalIcon(signalPreviewColour(entry?.data,phase,entry?.at||0),phase));
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
  $('show-signal-layout').onchange=paintSignalMarkers;
  const timer=setInterval(()=>{if(map){map.on('zoomend',paintSignalMarkers);clearInterval(timer);updateSignalMap();}},200);
  setInterval(updateSignalMap,1000);
});
