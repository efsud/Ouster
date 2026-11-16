'use strict';
const directionIndicators={layer:null,markers:new Map(),region:null,busy:false,updated:0};
const directionOffset={N:[0,38],S:[0,-38],E:[38,0],W:[-38,0]};
const throughMovement={N:'SN',S:'NS',E:'WE',W:'EW'};
function directionIcon(direction,status,estimated=false){
  const colours={RED:'#e34848',YELLOW:'#ffc840',GREEN:'#34c978',UNKNOWN:'#83949c'};
  return L.divIcon({className:'direction-signal',iconSize:[44,68],iconAnchor:[22,34],html:`<div style="--signal-colour:${colours[status]||colours.UNKNOWN}"><b>${direction}${estimated?'~':''}</b><i></i><strong>${status==='UNKNOWN'?'?':status}</strong><small>${throughMovement[direction][0]}→${throughMovement[direction][1]}</small>${estimated?'<em>EST</em>':''}</div>`});
}
function resetDirectionIndicators(){
  if(!map)return;
  directionIndicators.layer??=L.layerGroup().addTo(map);
  directionIndicators.layer.clearLayers();directionIndicators.markers.clear();directionIndicators.region=$('region').value;
  for(const site of state.sites.filter(s=>s.region===directionIndicators.region)){
    const origin=site.reference_location;if(!origin)continue;
    for(const [d,[east,north]] of Object.entries(directionOffset)){
      const point=[origin.lat+north/111320,origin.lng+east/(111320*Math.cos(origin.lat*Math.PI/180))];
      const marker=L.marker(point,{icon:directionIcon(d,'UNKNOWN'),zIndexOffset:700,keyboard:false});
      marker.bindTooltip(`${site.name} · ${d}: ${throughMovement[d][0]} → ${throughMovement[d][1]} · mapping unverified · schematic position`);
      directionIndicators.markers.set(site.id+':'+d,{marker,site:site.id,d});
    }
  }
}
async function refreshDirectionIndicators(){
  if(!map||!state.sites.length)return;
  if(directionIndicators.region!==$('region').value)resetDirectionIndicators();
  if(Date.now()-directionIndicators.updated>5000)renderPhasePanel(null);
  const visible=state.tab==='live'&&map.getZoom()>=17&&$('show-direction-signals').checked;
  for(const {marker,d} of directionIndicators.markers.values()){
    if(Date.now()-directionIndicators.updated>5000)marker.setIcon(directionIcon(d,'UNKNOWN'));
    if(visible&&!directionIndicators.layer.hasLayer(marker))directionIndicators.layer.addLayer(marker);
    if(!visible&&directionIndicators.layer.hasLayer(marker))directionIndicators.layer.removeLayer(marker);
  }
  if(state.tab!=='live'||directionIndicators.busy)return;
  const region=$('region').value;directionIndicators.busy=true;
  try{
    const result=await api('/api/directional-signals?region='+encodeURIComponent(region));
    if(region!==$('region').value)return;
    directionIndicators.updated=Date.now();
    renderPhasePanel(result.snapshots.find(s=>s.site===state.site?.id));
    let confirmed=0,estimated=0;
    for(const s of result.snapshots)for(const d of s.directions){
      const item=directionIndicators.markers.get(s.site+':'+d.direction);if(!item)continue;
      if(d.status!=='UNKNOWN'){if(d.estimated)estimated++;else confirmed++;}
      item.marker.setIcon(directionIcon(d.direction,d.status,d.estimated));
      const tip=document.createElement('span');tip.textContent=`${d.direction} indicator · ${d.movement[0]} → ${d.movement[1]} · ${d.status} · ${d.reason}. ${d.estimated?'ESTIMATED — not verified. ':''}${d.definition_check?.conflict?'DEFINITION CONFLICT — check orientation and label/number mapping. ':''}${d.estimation?.matched_releases??0} straight-through releases; candidates: ${(d.estimation?.candidates||[]).map(c=>`${c.phase} (score ${c.score}, ${c.cycles} cycles)`).join(', ')||'none'}. Schematic location. ${s.checks.join('; ')} Vehicle/signal timing not verified.`;
      item.marker.setTooltipContent(tip);
    }
    $('direction-signal-status').textContent=`${confirmed} verified, ${estimated} ESTIMATED directional colors (~). Estimates require fresh streams and repeated stop/release evidence. Gray = unknown mapping, stale or unavailable. Opposing directions are not forced to match.`;
  }catch{
    directionIndicators.updated=0;
    renderPhasePanel(null);
    for(const {marker,d} of directionIndicators.markers.values())marker.setIcon(directionIcon(d,'UNKNOWN'));
    $('direction-signal-status').textContent='Signal state unavailable; indicators remain gray.';
  }finally{directionIndicators.busy=false;}
}
setInterval(refreshDirectionIndicators,1000);

function renderPhasePanel(snapshot){
  const title=$('live-phase-title'),health=$('live-phase-health'),cards=$('live-phase-cards'),extra=$('live-phase-extra');
  title.textContent='Live API phases · '+(state.site?.name||'Select an intersection');
  cards.replaceChildren();extra.replaceChildren();$('phase-direction-evidence').replaceChildren();
  if(!snapshot){health.textContent='Phase data unavailable. No current colors can be shown.';return;}
  health.textContent=(snapshot.stream_receiving?'Receiving':'Stale / disconnected')+' · '+(snapshot.absolute_received?'Absolute phase snapshot received':'Waiting for initialization')+' · '+(snapshot.phases||[]).length+' reported phase entries (not physical lights).';
  let hidden=0;
  for(const p of snapshot.phases||[]){
    const card=document.createElement('div');card.className='phase-card';
    const label=document.createElement('b');label.textContent='Phase '+p.phase;
    const color=document.createElement('strong');color.textContent=p.status;color.dataset.status=p.status;
    const age=document.createElement('small');age.textContent=p.status==='UNKNOWN'?'No confirmed current state':p.status==='INVALID'?'API code 0 · invalid':`${p.age_s}s since received phase update`;
    card.append(label,color,age);card.title='Sensor timestamp (timezone unverified): '+(p.sensor_timestamp||'unavailable');
    if(p.last_received_status==='INVALID'){extra.append(card);hidden++;}else cards.append(card);
  }
  $('phase-extra-summary').textContent=`${hidden} invalid phase entries (API code 0)`;
  for(const d of snapshot.directions){
    const line=document.createElement('p');
    line.textContent=`${d.direction} (${d.movement[0]}→${d.movement[1]}): ${d.status}${d.estimated?' · EST':''} — ${d.reason}. ${d.estimation?.matched_releases||0} qualifying vehicle departures.`;
    $('phase-direction-evidence').append(line);
  }
}
