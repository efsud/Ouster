'use strict';
const directionIndicators={layer:null,markers:new Map(),region:null,busy:false,updated:0};
const directionOffset={N:[0,38],S:[0,-38],E:[38,0],W:[-38,0]};
const throughMovement={N:'SN',S:'NS',E:'WE',W:'EW'};
function directionIcon(direction,status){
  const colours={RED:'#e34848',YELLOW:'#ffc840',GREEN:'#34c978',UNKNOWN:'#83949c'};
  return L.divIcon({className:'direction-signal',iconSize:[30,42],iconAnchor:[15,21],html:`<div style="--signal-colour:${colours[status]||colours.UNKNOWN}"><b>${direction}</b><i></i><small>${throughMovement[direction][0]}→${throughMovement[direction][1]}</small></div>`});
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
  const visible=state.tab==='live'&&map.getZoom()>=17&&$('show-direction-signals').checked;
  for(const {marker,d} of directionIndicators.markers.values()){
    if(Date.now()-directionIndicators.updated>5000)marker.setIcon(directionIcon(d,'UNKNOWN'));
    if(visible&&!directionIndicators.layer.hasLayer(marker))directionIndicators.layer.addLayer(marker);
    if(!visible&&directionIndicators.layer.hasLayer(marker))directionIndicators.layer.removeLayer(marker);
  }
  if(!visible||directionIndicators.busy)return;
  const region=$('region').value;directionIndicators.busy=true;
  try{
    const result=await api('/api/directional-signals?region='+encodeURIComponent(region));
    if(region!==$('region').value)return;
    directionIndicators.updated=Date.now();
    let confirmed=0;
    for(const s of result.snapshots)for(const d of s.directions){
      const item=directionIndicators.markers.get(s.site+':'+d.direction);if(!item)continue;
      if(d.status!=='UNKNOWN')confirmed++;
      item.marker.setIcon(directionIcon(d.direction,d.status));
      const tip=document.createElement('span');tip.textContent=`${d.direction} indicator · ${d.movement[0]} → ${d.movement[1]} · ${d.status} · ${d.reason}. Schematic location. ${s.checks.join('; ')} Vehicle/signal timing not verified.`;
      item.marker.setTooltipContent(tip);
    }
    $('direction-signal-status').textContent=`${confirmed} verified directional colors. Gray = unknown mapping, stale or unavailable. Opposing directions are not forced to match.`;
  }catch{
    directionIndicators.updated=0;
    for(const {marker,d} of directionIndicators.markers.values())marker.setIcon(directionIcon(d,'UNKNOWN'));
    $('direction-signal-status').textContent='Signal state unavailable; indicators remain gray.';
  }finally{directionIndicators.busy=false;}
}
setInterval(refreshDirectionIndicators,1000);
