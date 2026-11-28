'use strict';
// These boundaries summarize observed support; they never bridge an empty bin.
function regimeEnvelopeRuns(envelope, binSeconds=1) {
 const runs=[];let run=[],previous=null;
 for(const row of envelope||[]){
  const bin=Math.floor(row[0]/binSeconds);
  if(previous!==null&&bin>previous+1){if(run.length)runs.push(run);run=[];}
  run.push(row);previous=bin;
 }
 if(run.length)runs.push(run);return runs;
}
function regimeSegmentContains(member, edgeEndIndex){return edgeEndIndex>member.start_index&&edgeEndIndex<=member.end_index;}
const regimeEnabled=()=>Boolean(document.getElementById('regime-mode')?.checked);
function regimePathKey(path){return JSON.stringify([path.site,path.identity_key,path.points?.[0]?.[0],path.points?.at(-1)?.[0]]);}
function sameRegimeSnapshot(snapshot,layers){return Boolean(snapshot&&layers?.snapshot_generated_at===snapshot.generated_at&&layers?.regime_groups?.snapshot_generated_at===snapshot.generated_at);}
function regimeData(){return sameRegimeSnapshot(data,reconstruction)?reconstruction.regime_groups:null;}
function regimeSelection(){return regimeEnabled()&&regimeData()?(el('regime-select')?.value||'all'):'all';}
function regimeMatchesKind(group){const kind=el('regime-kind')?.value||'all';return kind==='all'||group.regime===kind;}
function regimeEntries(){
 const selected=new Set([...el('sites').querySelectorAll('input:checked')].map(n=>n.value));
 const filter=el('objects').value;
 return (regimeData()?.sites||[]).filter(s=>selected.has(s.id)).flatMap(s=>s.groups.filter(g=>{
  if(g.direction!==el('direction').value||!regimeMatchesKind(g))return false;
  const original=data.sites.find(v=>v.id===s.id);
  return ['all','vehicles'].includes(filter)&&g.member_indices.every(i=>vehicle.has(original.tracks[i].class_type));
 }).map(g=>({site:s,group:g,key:groupKey(s.id,g.group_id)})));
}
function updateRegimeControls(){
 if(!el('regime-controls'))return;
 const select=el('regime-select'),previous=select.value,study=regimeData();select.replaceChildren(new Option('All local groups','all'));
 const entries=regimeEntries();
 const learned=study?(reconstruction.regime_estimates||[]):[];
 el('regime-learned').disabled=!learned.length;el('regime-learned-example').disabled=!learned.length;
 const audit=study?reconstruction.regime_learning_review:null;
 el('regime-learned-status').textContent=study?`${learned.length} optional learned refinements in this hour; ${audit?.attempted||0} eligible gaps checked within the processing budget. They change estimated shapes of supported same-ID gaps, not the number of verified vehicle matches.`:'Waiting for learned candidates aligned with this hour.';
 for(const {site,group:g,key} of entries)select.add(new Option(`${site.name} · ${g.regime} · ${g.identity_count} IDs · ${clock(data.start+g.start_s)}`,key));
 if([...select.options].some(o=>o.value===previous))select.value=previous;
 el('regime-example').disabled=!entries.length;select.disabled=!entries.length;
 el('regime-status').textContent=study?`${entries.length} local groups in the selected intersections and direction. Similar numeric speed and slope, nearby time and road position; at least three independent local IDs per group. Initial zero-speed artifacts do not count as stops.`:'Waiting for segment groups aligned with this recorded hour. Recorded trajectories remain visible.';
 const host=el('regime-validation');host.replaceChildren();
 for(const note of study?.learning_notes||['The new learned estimator is being evaluated. Existing supported estimates remain available.']){const p=document.createElement('p');p.textContent=note;host.append(p);}
}
function regimeAllows(siteId,trackIndex,edgeEndIndex){
 const chosen=regimeSelection();if(chosen==='all')return true;
 const assignments=regimeData()?.sites.find(s=>s.id===siteId)?.assignments[trackIndex]||[];
 return assignments.some(m=>groupKey(siteId,m.group_id)===chosen&&regimeSegmentContains(m,edgeEndIndex));
}
function regimeAllowsEstimate(path){
 const chosen=regimeSelection();if(chosen==='all')return true;
 const entry=regimeEntries().find(e=>e.key===chosen);if(!entry||path.site!==entry.site.id)return false;
 const site=data.sites.find(s=>s.id===entry.site.id),key=path.identity_key||path.source_key?.slice(0,2);
 if(!key||!path.points?.length)return false;
 const identity=JSON.stringify(key.map(String));
 return entry.group.members.some(m=>JSON.stringify(site.tracks[m.track_index].source_key?.slice(0,2).map(String))===identity&&path.points[0][0]<=m.end_s+20&&path.points.at(-1)[0]>=m.start_s-20);
}
function inspectRegime(key){
 const entry=regimeEntries().find(e=>e.key===key);if(!entry||!data)return;
 const {site,group:g}=entry;el('regime-mode').checked=true;
 if(el('group-mode')){el('group-mode').checked=false;groupModeUI();}
 for(const box of el('sites').querySelectorAll('input'))box.checked=box.value===site.id;
 updateRegimeControls();el('regime-select').value=key;
 const a=g.aggregate;
 el('regime-detail').textContent=`${site.name} · ${g.regime} · ${g.identity_count} distinct local IDs, ${g.members.length} observed segments. Median speed ${a.speed_median_mps.toFixed(1)} m/s (IQR ${a.speed_iqr_mps.toFixed(1)}); median slope ${a.slope_median_mps.toFixed(1)} m/s. These statistics describe members, not an average vehicle. Blue outlines stop where observed support is absent.`;
 view=[Math.max(data.start,data.start+g.start_s-5),Math.min(data.end,data.start+g.end_s+5)];
 draw();el('plot').scrollIntoView({block:'center'});
}
function drawRegimeGroups(c,x,y){
 if(!regimeEnabled()||!regimeData())return;
 // Group support counts are for retained vehicle classes. Do not show vehicle
 // envelopes behind a cyclist/pedestrian-only view or a legacy group filter.
 if(!['all','vehicles'].includes(el('objects').value)||isGrouped()&&selectedGroup()!=='all')return;
 const chosen=regimeSelection();c.save();c.strokeStyle='#2766dc';c.lineWidth=1.3;c.setLineDash([6,5]);
 for(const {group:g,key} of regimeEntries()){
  if(chosen!=='all'&&key!==chosen||data.start+g.end_s<view[0]||data.start+g.start_s>view[1])continue;
  for(const run of regimeEnvelopeRuns(g.envelope,g.envelope_bin_s||1)){
   if(run.length<2)continue;
   // No convex hull across sensors, missing bins, or different groups.
   c.beginPath();run.forEach((r,i)=>{const xx=x(data.start+r[0]),yy=y(r[1])+3;i?c.lineTo(xx,yy):c.moveTo(xx,yy);});
   for(const r of [...run].reverse())c.lineTo(x(data.start+r[0]),y(r[2])-3);
   c.closePath();c.stroke();
  }
 }
 c.restore();
}
function initializeRegimeControls(){
 if(!el('regime-controls'))return;
 el('regime-mode').onchange=()=>{if(regimeEnabled()){el('group-mode').checked=false;groupModeUI();}draw();};
 el('regime-learned').onchange=draw;
 el('regime-learned-example').onclick=()=>{
  const path=regimeData()?(reconstruction.regime_estimates||[])[0]:null;if(!path)return;
  el('regime-learned').checked=true;el('regime-mode').checked=true;el('regime-select').value='all';el('regime-kind').value='all';el('group-mode').checked=false;
  el('direction').value=path.direction;el('objects').value='vehicles';
  for(const box of el('sites').querySelectorAll('input'))box.checked=box.value===path.site;
  view=[Math.max(data.start,data.start+path.points[0][0]-8),Math.min(data.end,data.start+path.points.at(-1)[0]+8)];
  updateGroupControls();el('regime-detail').textContent='Purple dashed: experimental group-learned shape for a supported same-ID gap. Solid speed-colored lines are observations; blue outlines summarize nearby observed groups. This preview replaces only the corresponding baseline estimate on screen.';
  draw();el('plot').scrollIntoView({block:'center'});
 };
 el('regime-kind').onchange=()=>{updateRegimeControls();draw();};
 el('regime-select').onchange=()=>{if(regimeSelection()==='all')draw();else inspectRegime(regimeSelection());};
 el('regime-example').onclick=()=>{const entries=regimeEntries();if(entries.length)inspectRegime(entries[0].key);};
 el('regime-reset').onclick=()=>{el('regime-select').value='all';el('regime-kind').value='all';for(const box of el('sites').querySelectorAll('input'))box.checked=true;el('regime-detail').textContent='Solid individual paths keep their speed colors. Blue boundaries summarize observed support; they are not reconstructed vehicle paths.';if(data)view=[data.start,data.end];updateRegimeControls();draw();};
}
if(typeof module!=='undefined')module.exports={regimeEnvelopeRuns,regimeSegmentContains,sameRegimeSnapshot};
