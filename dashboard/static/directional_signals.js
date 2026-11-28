'use strict';
// Live API phase panel only; no schematic signal locations on the map.
const phasePanelPoll={busy:false,updated:0};
async function refreshPhasePanel(){
  if(!state.sites.length)return;
  if(Date.now()-phasePanelPoll.updated>5000){renderPhasePanel(null);renderFinchGroups([]);}
  if(state.tab!=='live'||phasePanelPoll.busy)return;
  const region=$('region').value;phasePanelPoll.busy=true;
  try{
    const result=await api('/api/directional-signals?region='+encodeURIComponent(region));
    if(region!==$('region').value)return;
    phasePanelPoll.updated=Date.now();
    renderFinchGroups(result.snapshots);
    renderPhasePanel(result.snapshots.find(s=>s.site===state.site?.id));
  }catch{
    phasePanelPoll.updated=0;renderPhasePanel(null);renderFinchGroups([]);
  }finally{phasePanelPoll.busy=false;}
}
setInterval(refreshPhasePanel,1000);

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

let finchMovementLayer=null;
function renderFinchGroups(snapshots){
  const panel=$('finch-groups-panel'),list=$('finch-group-evidence');
  panel.hidden=$('region').value!=='Toronto';
  if(map){finchMovementLayer??=L.layerGroup().addTo(map);finchMovementLayer.clearLayers();}
  list.replaceChildren();if(panel.hidden)return;
  const selected=snapshots.find(s=>s.site===state.site?.id);
  if(!selected){list.textContent='Waiting for current group observations.';return;}
  for(const g of selected.movement_groups||[]){
    const line=document.createElement('p');
    line.textContent=`P${g.labels.join('+')} · ${g.movements.join(', ')} · ${g.status} · DOC EST — ${g.proposed_group.length>1?'Document candidate P'+g.proposed_group.join('+')+': '+(100*(g.group_evidence.agreement||0)).toFixed(1)+'% observed state agreement. ':''}${g.evidence.samples||0} samples, ${g.evidence.span_s||0}s. ${g.labels.length===1&&g.evidence.eligible?'Repeated phase cycles observed; single phase, not a merged group':g.evidence.reason||'Waiting for observation'}. Placement: ${g.placement_reason}. ${g.flow_conflicts.length?'Vehicle-direction conflict: '+g.flow_conflicts.join(', '):g.flow_support.length?'Vehicle-flow support: '+g.flow_support.join(', '):'Vehicle-flow direction unconfirmed'}.`;
    list.append(line);
  }
  if(!map||state.tab!=='live'||map.getZoom()<17||!$('show-finch-groups').checked)return;
  for(const s of snapshots){
    const site=state.sites.find(x=>x.id===s.site),origin=site?.reference_location;if(!origin)continue;
    const offsets={N:[0,42],S:[0,-42],E:[42,0],W:[-42,0]},slots={};
    for(const g of s.movement_groups||[]){
      if(!g.show_on_map||!offsets[g.destination])continue;
      const base=offsets[g.destination],slot=slots[g.destination]||0;slots[g.destination]=slot+1;
      const cross=(slot%2?1:-1)*Math.ceil(slot/2)*25;
      const east=base[0]+(base[0]===0?cross:0),north=base[1]+(base[1]===0?cross:0);
      const el=document.createElement('div');el.className='finch-group-light';el.dataset.status=g.status;
      const label=document.createElement('b');label.textContent='P'+g.labels.join('+');
      const color=document.createElement('strong');color.textContent=g.status;
      const movement=document.createElement('small');movement.textContent=g.movements.join(' / ');
      const badge=document.createElement('small');badge.textContent='DOC EST';el.append(label,color,movement,badge);
      const marker=L.marker([origin.lat+north/111320,origin.lng+east/(111320*Math.cos(origin.lat*Math.PI/180))],{icon:L.divIcon({className:'finch-group-marker',html:el.outerHTML,iconSize:[72,68],iconAnchor:[36,34]}),zIndexOffset:650,keyboard:false});
      const tip=document.createElement('span');tip.textContent=site.name+' · '+g.note+' '+g.evidence.reason;
      marker.bindTooltip(tip);finchMovementLayer.addLayer(marker);
    }
  }
}
