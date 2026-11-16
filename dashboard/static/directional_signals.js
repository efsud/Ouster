'use strict';
// Live API phase panel only; no schematic signal locations on the map.
const phasePanelPoll={busy:false,updated:0};
async function refreshPhasePanel(){
  if(!state.sites.length)return;
  if(Date.now()-phasePanelPoll.updated>5000)renderPhasePanel(null);
  if(state.tab!=='live'||phasePanelPoll.busy)return;
  const region=$('region').value;phasePanelPoll.busy=true;
  try{
    const result=await api('/api/directional-signals?region='+encodeURIComponent(region));
    if(region!==$('region').value)return;
    phasePanelPoll.updated=Date.now();
    renderPhasePanel(result.snapshots.find(s=>s.site===state.site?.id));
  }catch{
    phasePanelPoll.updated=0;renderPhasePanel(null);
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
