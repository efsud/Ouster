'use strict';
// Display-only alternatives. Never modify observations, accepted associations,
// stored reconstruction outputs, vehicle identities or KPI inputs.
(function(root){
 const vehicles=new Set(['1','2','3','4','5','6','7','8','9','15']);
 const median=xs=>{const s=xs.slice().sort((a,b)=>a-b),n=s.length;return n?s[Math.floor(n/2)]:0;};
 const quantile=(xs,q)=>{const s=xs.slice().sort((a,b)=>a-b);return s[Math.floor((s.length-1)*q)];};
 const key=(site,index)=>site+'|'+index;
 function endpoint(track,departure){
  const p=track.points;if(!p||p.length<3)return null;
  const anchor=p[departure?p.length-1:0];if(!anchor.slice(0,2).every(Number.isFinite))return null;
  const slopes=[];let span=0;
  for(let n=1;n<p.length&&n<=8;n++){
   const a=p[departure?p.length-n-1:n-1],b=p[departure?p.length-n:n],dt=b[0]-a[0];
   if(!(dt>0&&dt<=1.5)||!Number.isFinite((b[1]-a[1])/dt))break;
   if(Math.max(Math.abs(a[0]-anchor[0]),Math.abs(b[0]-anchor[0]))>3)break;
   slopes.push((b[1]-a[1])/dt);span+=dt;
  }
  if(slopes.length<2||span<.5)return null;
  const v=median(slopes);if(Math.abs(v)>35)return null;
  return {t:anchor[0],x:anchor[1],v};
 }
 function reservations(snapshot,layers){
  const used={departure:new Set(),arrival:new Set()},index=new Map();
  for(const s of snapshot.sites)for(const [i,tr] of s.tracks.entries()){
   if(!tr.points?.length)continue;
   for(const side of ['departure','arrival']){
    const p=tr.points[side==='departure'?tr.points.length-1:0],bucket=s.id+'|'+side+'|'+Math.floor(p[0]*10);
    if(!index.has(bucket))index.set(bucket,[]);index.get(bucket).push({i,p});
   }
  }
  function reserve(site,side,p,ref){
   if(ref?.site===site)for(const i of ref.source_fragment_indices||[])used[side].add(key(site,i));
   if(!p)return;
   for(let d=-1;d<=1;d++)for(const item of index.get(site+'|'+side+'|'+(Math.floor(p[0]*10)+d))||[]){
    if(Math.abs(item.p[0]-p[0])<.06&&Math.abs(item.p[1]-p[1])<=.11)used[side].add(key(site,item.i));
   }
  }
  for(const source of [layers,layers.residual_color,layers.trajectory_groups]){
   for(const path of [...(source?.within_intersection||[]),...(source?.between_intersections||[])]){
    if(!path.points?.length)continue;
    const ids=path.sites||[path.site,path.site];
    reserve(ids[0],'departure',path.points[0],path.endpoint_provenance?.departure);
    reserve(ids.at(-1),'arrival',path.points.at(-1),path.endpoint_provenance?.arrival);
   }
  }
  return used;
 }
 function endpoints(site,direction,departure,used){
  const sign=direction==='eastbound'?1:-1,side=departure?'departure':'arrival',out=[];
  for(const [i,tr] of site.tracks.entries()){
   if(tr.method||tr.direction!==direction||!vehicles.has(String(tr.class_type))||used[side].has(key(site.id,i)))continue;
   const m=tr.movement,unknown=!m||m.state==='unknown';
   const flag=departure?'can_match_next':'can_match_previous',route=departure?'outgoing_direction':'incoming_direction';
   if(!unknown&&(m[flag]===false||(m[route]&&m[route]!==direction)))continue;
   const e=endpoint(tr,departure);if(!e||e.v*sign<-.7)continue;
   out.push({...e,v:Math.max(0,e.v*sign)*sign,site:site.id,index:i,unknown,
    class_type:String(tr.class_type),source_key:tr.source_key||[],shape:tr[departure?'shape_end':'shape_start']});
  }
  if(!out.length)return [];
  const edge=quantile(out.map(e=>e.x*sign),departure?.9:.1);
  return out.filter(e=>Math.abs(e.x*sign-edge)<=60);
 }
 function score(a,b,sign,maxDistance){
  const dt=b.t-a.t,dx=(b.x-a.x)*sign;
  if(!(dt>0&&dt<=180&&dx>2&&dx<=maxDistance&&dx/dt<=35))return null;
  const va=a.v*sign,vb=b.v*sign,mean=(va+vb)/2;
  // A 30 m tolerance overwhelmed the evidence in 3–10 m gaps. Scale the
  // position residual to the actual gap, so a later platoon is not a cheap fit.
  let cost=Math.abs(dx-mean*dt)/Math.max(5,.35*dx)+Math.abs(va-vb)/8+dt/360;
  if(a.unknown||b.unknown)cost+=.4;
  if(a.class_type!==b.class_type)cost+=.2;
  if(a.shape&&b.shape)cost+=Math.min(1,Math.abs(a.shape.length_m-b.shape.length_m)/4);
  return Number.isFinite(cost)&&cost<=4?cost:null;
 }
 function motion(a,b,sign){
  const dt=b.t-a.t,dx=(b.x-a.x)*sign,mean=dx/dt;
  const v0=Math.max(0,a.v*sign),v1=Math.max(0,b.v*sign);
  // Preserve measured endpoint slopes. Never slow both endpoints to make an
  // incompatible association fit. Check the entire polynomial, not only samples.
  const c2=3*mean-2*v0-v1,c3=v0+v1-2*mean;
  const speeds=[v0,v1],turn=Math.abs(c3)>1e-12?-c2/(3*c3):-1;
  if(turn>0&&turn<1)speeds.push(v0+2*c2*turn+3*c3*turn*turn);
  if(speeds.some(v=>!Number.isFinite(v)||v< -1e-8||v>35)||
     Math.max(Math.abs(2*c2/dt),Math.abs((2*c2+6*c3)/dt))>6)return null;
  return {dt,dx,v0,v1,c2,c3};
 }
 function curve(a,b,sign,m){
  const {dt,v0,c2,c3}=m;
  const out=[],n=Math.max(12,Math.ceil(dt));
  for(let i=0;i<=n;i++){
   const u=i/n,u2=u*u,u3=u2*u;
   const distance=dt*(v0*u+c2*u2+c3*u3),v=v0+2*c2*u+3*c3*u2;
   out.push([a.t+dt*u,a.x+sign*distance,Math.max(0,v)]);
  }
  out[0][1]=a.x;out[n][1]=b.x;return out;
 }
 function build(snapshot,layers){
  const result={paths:[],links:[],method:'uncertain_endpoint_assignment_v2',kpi_eligible:false};
  if(!snapshot?.sites||layers?.state!=='ready'||snapshot.generated_at!==layers.snapshot_generated_at)return result;
  const used=reservations(snapshot,layers),sites=snapshot.sites.slice().sort((a,b)=>a.station_m-b.station_m);
  for(let k=0;k<sites.length-1;k++)for(const direction of ['eastbound','westbound']){
   const sign=direction==='eastbound'?1:-1,[up,down]=sign===1?[sites[k],sites[k+1]]:[sites[k+1],sites[k]];
   const aa=endpoints(up,direction,true,used),bb=endpoints(down,direction,false,used).sort((a,b)=>a.t-b.t||a.index-b.index);
   const maxDistance=Math.min(600,Math.abs(down.station_m-up.station_m)+260),edges=[];let start=0;
   aa.sort((a,b)=>a.t-b.t||a.index-b.index);
   for(const a of aa){
    while(start<bb.length&&bb[start].t<=a.t)start++;
    const options=[];
    for(let j=start;j<bb.length&&bb[j].t<=a.t+180;j++){
     const b=bb[j],cost=score(a,b,sign,maxDistance);if(cost===null)continue;
     const m=motion(a,b,sign);if(m)options.push({a,b,cost,m});
    }
    options.sort((a,b)=>a.cost-b.cost||a.b.t-b.b.t||a.b.index-b.b.index);
    edges.push(...options.slice(0,10));
   }
   // No uniqueness-margin requirement: ties are deliberate best guesses here.
   edges.sort((a,b)=>a.cost-b.cost||a.a.t-b.a.t||a.a.index-b.a.index||a.b.index-b.b.index);
   let count=0;
   for(const {a,b,cost,m} of edges){
    const ak=key(a.site,a.index),bk=key(b.site,b.index);
    if(used.departure.has(ak)||used.arrival.has(bk))continue;
    const points=curve(a,b,sign,m);
    used.departure.add(ak);used.arrival.add(bk);count++;
    result.paths.push({sites:[up.id,down.id],direction,class_type:a.class_type,points,
     layer:'uncertain_between',method:result.method,identity:'unverified_best_guess',kpi_eligible:false,
     speed_available:false,association_cost:cost,
     endpoint_provenance:{departure:{site:a.site,source_fragment_indices:[a.index],source_key:a.source_key},
      arrival:{site:b.site,source_fragment_indices:[b.index],source_key:b.source_key},cross_sensor_identity_verified:false}});
   }
   result.links.push({sites:[up.id,down.id],direction,departures:aa.length,arrivals:bb.length,added:count});
  }
  return result;
 }
 const api={build};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.UncertainConnections=api;
})(typeof globalThis!=='undefined'?globalThis:this);
