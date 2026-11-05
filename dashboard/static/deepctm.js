'use strict';
(() => {
  const el=id=>document.getElementById(id), names={'OBC-AG-SA-C257220':'Weston','OBC-AG-SA-C251071':'Signet / Arrow'};
  let report=null;
  const fmt=v=>Number.isFinite(v)?v.toFixed(1):'—';
  function cell(row,value){const td=document.createElement('td');td.textContent=value;row.append(td);}
  function render(){
    const d=report?.directions?.[el('forecast-direction').value];el('forecast-metrics').replaceChildren();el('forecast-chart').replaceChildren();
    if(!d){el('forecast-status').textContent='No trained results yet. Short recordings test reception; training requires sufficient complete windows.';return;}
    el('forecast-status').textContent=d.state==='insufficient_data'?d.reason:`Provisional model · ${d.sequences.train} training, ${d.sequences.validation} validation, ${d.sequences.test} test sequences. Best epoch ${d.best_epoch}.`;
    if(!d.metrics)return;
    const table=document.createElement('table'),head=document.createElement('tr');['Forecast horizon','DeepCTM RMSE, both sites (veh/h)','Persistence RMSE','Pure CTM RMSE'].forEach(x=>cell(head,x));table.append(head);
    for(const lead of ['15','60']){const row=document.createElement('tr');[`${lead} minutes`,fmt(d.metrics[lead].rmse_veh_h),fmt(d.persistence[lead].rmse_veh_h),fmt(d.pure_ctm[lead].rmse_veh_h)].forEach(x=>cell(row,x));table.append(row);}
    el('forecast-metrics').append(table);
    const detail=document.createElement('p');detail.textContent=`Mass-balance discrepancy: ${fmt(d.mmce_mean_all_cells_vehicles)} vehicles per cell/step. Neural corrections are not guaranteed conservative.`;el('forecast-metrics').append(detail);
    // Show one horizon and endpoint at a time; never mix forecast lead times.
    const selected=Number(el('forecast-site').value),node=el('forecast-direction').value==='eastbound'?selected:2-selected;
    const points=d.held_out_forecasts.filter(p=>p.lead_minutes===15&&p.node===node);
    const caption=document.createElement('p');caption.textContent=`${selected===0?'Weston':'Signet / Arrow'} · 15-minute flow forecasts. Blue: predicted; green: observed provisional input. Dates use your local timezone.`;el('forecast-chart').append(caption);
    if(!points.length)return;
    const ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg');svg.setAttribute('viewBox','0 0 900 240');svg.setAttribute('role','img');svg.setAttribute('aria-label','Observed and predicted held-out traffic flow');
    const max=Math.max(1,...points.flatMap(p=>[p.observed_flow,p.predicted_flow]));const first=points[0].target_start,last=points.at(-1).target_start;
    for(const [key,color] of [['predicted_flow','#426fba'],['observed_flow','#17a990']]){
      const path=document.createElementNS(ns,'path');let prev=null;
      path.setAttribute('d',points.map(p=>{const move=prev===null||p.target_start-prev>900?'M':'L';prev=p.target_start;return `${move}${50+(p.target_start-first)/Math.max(900,last-first)*800},${200-p[key]/max*170}`;}).join(' '));path.setAttribute('stroke',color);path.setAttribute('fill','none');path.setAttribute('stroke-width','2');svg.append(path);
    }
    el('forecast-chart').append(svg);const dates=document.createElement('p');dates.textContent=`${new Date(first*1000).toLocaleString()} – ${new Date((last+900)*1000).toLocaleString()} · y-axis 0–${fmt(max)} veh/h`;el('forecast-chart').append(dates);
  }
  async function refresh(){try{
    const response=await fetch('/api/deepctm');if(!response.ok)throw new Error('Status unavailable');const data=await response.json();
    el('capture-status').textContent=`Experiment: ${data.state}${data.error?' · '+data.error:''}`;
    el('capture-time').textContent=data.start?`Start: ${new Date(data.start*1000).toLocaleString()} · Scheduled end: ${new Date(data.end*1000).toLocaleString()}`:'';
    el('capture-sensors').replaceChildren();for(const s of data.sensors){const row=document.createElement('tr');[names[s.site]||s.site,s.receiving_now?'Receiving now':`${s.state} · no fresh frames`,s.frames||0,s.last_receipt?new Date(s.last_receipt*1000).toLocaleString():'None'].forEach(v=>cell(row,v));el('capture-sensors').append(row);}
    el('forecast-assumptions').replaceChildren();for(const text of data.assumptions||[]){const li=document.createElement('li');li.textContent=text;el('forecast-assumptions').append(li);}
    report=data.report;render();
  }catch(e){el('capture-status').textContent=e.message;}}
  el('forecast-site').addEventListener('change',render);el('forecast-direction').addEventListener('change',render);refresh();setInterval(refresh,5000);
})();
