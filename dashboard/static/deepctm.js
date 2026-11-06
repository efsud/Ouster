'use strict';
(() => {
  const el=id=>document.getElementById(id), names={'OBC-AG-SA-C257220':'Weston','OBC-AG-SA-C251071':'Signet / Arrow'};
  let report=null, figuresLoaded=false, figuresBusy=false, captureId=null;
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
    el('experiment-title').textContent=data.title||'Finch corridor recordings';
    if(captureId!==data.capture_id){captureId=data.capture_id;figuresLoaded=false;el('recorded-figure').replaceChildren();el('recorded-figure-image').hidden=true;}
    if(!figuresLoaded)loadFigures();
    el('capture-status').textContent=`Experiment: ${data.state}${data.error?' · '+data.error:''}`;
    el('capture-time').textContent=data.start?`Start: ${new Date(data.start*1000).toLocaleString()} · Scheduled end: ${new Date(data.end*1000).toLocaleString()}`:'';
    el('capture-sensors').replaceChildren();for(const s of data.sensors){const row=document.createElement('tr');[s.name||names[s.site]||s.site,s.receiving_now?'Receiving now':`${s.state}${s.error?' · '+s.error:''} · no fresh frames`,s.frames||0,s.last_receipt?new Date(s.last_receipt*1000).toLocaleString():'None'].forEach(v=>cell(row,v));el('capture-sensors').append(row);}
    el('forecast-assumptions').replaceChildren();for(const text of data.assumptions||[]){const li=document.createElement('li');li.textContent=text;el('forecast-assumptions').append(li);}
    report=data.report;render();
  }catch(e){el('capture-status').textContent=e.message;}}
  let trackCache=new Map(), plotSerial=0, hoverPoints=[], interactiveIndex=null;
  const toronto=t=>new Date(t*1000).toLocaleTimeString('en-CA',{timeZone:'America/Toronto',hour12:false});
  function setupInteractive(index){
    interactiveIndex=index;trackCache=new Map();el('track-sites').replaceChildren();
    index.sites.forEach((s,i)=>{const label=document.createElement('label'),box=document.createElement('input');box.type='checkbox';box.value=s.site;box.checked=['Weston','Signet'].includes(s.name);box.addEventListener('change',()=>drawSelected(index));label.append(box,document.createTextNode(' '+s.name+(s.accepted_fragments?'':' (no data)')));el('track-sites').append(label);});
    for(const [id,checked] of [['tracks-all',true],['tracks-none',false]])el(id).onclick=()=>{el('track-sites').querySelectorAll('input').forEach(b=>b.checked=checked);drawSelected(index);};
  }
  async function drawSelected(index){
    const serial=++plotSerial,canvas=el('interactive-tracks'),ctx=canvas.getContext('2d');hoverPoints=[];
    const width=Math.max(600,canvas.clientWidth),height=700,ratio=window.devicePixelRatio||1;canvas.width=width*ratio;canvas.height=height*ratio;ctx.scale(ratio,ratio);ctx.fillStyle='white';ctx.fillRect(0,0,width,height);
    const selected=new Set([...el('track-sites').querySelectorAll('input:checked')].map(b=>b.value)),sites=index.sites.filter(s=>selected.has(s.site));
    if(!sites.length){el('interactive-status').textContent='Choose one or more intersections.';return;}
    const figure=index.figures.find(f=>f.file===el('recorded-figure').value);if(!figure)return;
    el('interactive-status').textContent='Loading selected recorded tracks…';
    try{
      const payloads=await Promise.all(sites.map(async s=>{if(!trackCache.has(s.site))trackCache.set(s.site,fetch('/api/deepctm/figures/'+s.site+'-tracks.json').then(r=>{if(!r.ok)throw Error('Interactive tracks are unavailable; original figures remain below.');return r.json();}).catch(e=>{trackCache.delete(s.site);throw e;}));return trackCache.get(s.site);}));
      if(serial!==plotSerial)return;
      const recordingStart=payloads[0].start,recordingEnd=payloads[0].end,match=figure.file.match(/-(\d+)\.png$/);
      const start=match?Math.max(recordingStart,Number(match[1])):recordingStart,end=match?Math.min(recordingEnd,Number(match[1])+300):recordingEnd;
      const min=sites[0].station_m-110,max=sites.at(-1).station_m+110,left=78,right=width-22,ph=235,tops=[50,390];
      const x=t=>left+(t-start)/(end-start)*(right-left),y=(station,top)=>top+ph-(station-min)/(max-min)*ph;
      const colors=['#2779ad','#d97813','#279640','#d13a42','#8652ad','#956240','#d35dba','#555','#9b9714','#279ca8'];let count=0;
      ctx.font='12px sans-serif';
      tops.forEach((top,panel)=>{
        ctx.fillStyle='#edf0f3';ctx.fillRect(left,top,right-left,ph);
        sites.forEach(s=>{ctx.fillStyle='#fff';ctx.fillRect(left,y(s.station_m+100,top),right-left,200/(max-min)*ph);});
        ctx.fillStyle='#223344';ctx.font='bold 14px sans-serif';ctx.fillText(panel?'Speed · red = slow, green = faster':'Measured tracks · colored by intersection',left,top-20);ctx.font='12px sans-serif';
        for(let i=0;i<=5;i++){const t=start+(end-start)*i/5;ctx.strokeStyle='#d8dde2';ctx.beginPath();ctx.moveTo(x(t),top);ctx.lineTo(x(t),top+ph);ctx.stroke();ctx.fillStyle='#334';ctx.textAlign=i===0?'left':i===5?'right':'center';ctx.fillText(toronto(t),x(t),top+ph+20);}ctx.textAlign='left';
        sites.forEach(s=>{const yy=y(s.station_m,top);ctx.fillStyle='#58636e';ctx.fillText(Math.round(s.station_m)+' m',5,yy+4);ctx.strokeStyle='#c4cbd2';ctx.setLineDash([3,4]);ctx.beginPath();ctx.moveTo(left,yy);ctx.lineTo(right,yy);ctx.stroke();ctx.setLineDash([]);});
      });
      sites.forEach((s,i)=>{const payload=payloads[i],color=colors[index.sites.findIndex(q=>q.site===s.site)%10];
        for(const tr of payload.tracks){if(tr.direction!==figure.direction)continue;const points=tr.points.filter(p=>payload.start+p[0]>=start&&payload.start+p[0]<=end);if(points.length<2)continue;count++;
          for(let j=1;j<points.length;j++){const a=points[j-1],b=points[j],t=payload.start+b[0];tops.forEach((top,panel)=>{ctx.strokeStyle=panel?`hsl(${Math.min(20,Math.max(0,b[2]))*6},75%,40%)`:color;ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(x(payload.start+a[0]),y(s.station_m+a[1],top));ctx.lineTo(x(t),y(s.station_m+b[1],top));ctx.stroke();});hoverPoints.push({x:x(t),y:y(s.station_m+b[1],tops[1]),upper:y(s.station_m+b[1],tops[0]),time:t,speed:b[2],name:s.name});}
        }
        tops.forEach(top=>{ctx.fillStyle=color;ctx.fillText(s.name+(s.accepted_fragments?'':' · no data'),left+5,y(s.station_m+95,top)+12);});
      });
      el('interactive-status').textContent=`${sites.length} intersections · ${figure.direction} · ${toronto(start)}–${toronto(end)} Toronto · ${count} measured fragments. Approximate alignment; no paths inferred between sites.`;
    }catch(e){if(serial===plotSerial)el('interactive-status').textContent=e.message;}
  }
  el('interactive-tracks').addEventListener('mousemove',event=>{const rect=event.currentTarget.getBoundingClientRect(),xx=(event.clientX-rect.left)*Math.max(600,rect.width)/rect.width,yy=event.clientY-rect.top;let nearest=null,dist=100;for(const p of hoverPoints){const d=(p.x-xx)**2+Math.min((p.y-yy)**2,(p.upper-yy)**2);if(d<dist){nearest=p;dist=d;}}el('track-hover').textContent=nearest?`${nearest.name} · ${toronto(nearest.time)} Toronto · ${nearest.speed.toFixed(1)} m/s (${(nearest.speed*3.6).toFixed(1)} km/h)`:'Move over a track to inspect its time and speed.';});
  window.addEventListener('resize',()=>{if(interactiveIndex)drawSelected(interactiveIndex);});

  async function loadFigures(){
    if(figuresBusy)return;figuresBusy=true;
    try {
      const response=await fetch('/api/deepctm/figures/index.json');if(!response.ok)throw new Error('Figures will appear here after this capture finishes and plotting completes.');
      const data=await response.json(), select=el('recorded-figure');select.replaceChildren();figuresLoaded=true;setupInteractive(data);
      for(const f of data.figures){const option=document.createElement('option');option.value=f.file;option.textContent=`${f.direction} · ${f.label} · ${f.fragments} track fragments`;select.append(option);}
      function show(){drawSelected(data);const url='/api/deepctm/figures/'+encodeURIComponent(select.value);el('recorded-figure-image').src=url;el('recorded-figure-image').hidden=false;el('recorded-figure-link').href=url;el('recorded-figure-status').textContent='Approximate corridor span: '+data.station_spacing_m.toFixed(0)+' m. No tracks are joined between sensors.';}
      select.onchange=show;if(select.options.length){select.selectedIndex=Math.min(1,select.options.length-1);show();}
    }catch(e){el('recorded-figure-status').textContent=e.message;}finally{figuresBusy=false;}
  }
  el('forecast-site').addEventListener('change',render);el('forecast-direction').addEventListener('change',render);refresh();setInterval(refresh,5000);
})();
