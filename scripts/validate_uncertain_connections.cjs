#!/usr/bin/env node
'use strict';
// Replay display-only associations against masked, recorded single-sensor data.
// This evaluates a spatial-gap proxy, not real cross-sensor vehicle identities.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const assert=require('node:assert/strict');
const args=Object.fromEntries(process.argv.slice(2).reduce((a,x,i,all)=>{
 if(x.startsWith('--'))a.push([x.slice(2),all[i+1]]);return a;
},[]));
if(!args.snapshot||!args.baseline||!args.out){
 console.error('Usage: node scripts/validate_uncertain_connections.cjs --snapshot file --baseline module.cjs --out report.json [--layers file]');
 process.exit(2);
}
const bytes=fs.readFileSync(args.snapshot),snapshot=JSON.parse(bytes);
const modules={before:path.resolve(args.baseline),after:path.resolve('dashboard/static/uncertain-connections.js')};
const models=Object.fromEntries(Object.entries(modules).map(([k,p])=>[k,require(p).build]));
const hash=x=>crypto.createHash('sha256').update(x).digest('hex');
const vehicles=new Set(['1','2','3','4','5','6','7','8','9','15']);
const mean=x=>x.length?x.reduce((a,b)=>a+b,0)/x.length:null;
const quantile=(x,q)=>x.length?x.slice().sort((a,b)=>a-b)[Math.floor((x.length-1)*q)]:null;
const tail=[2400,3600],widths=[5,15,40,80],rows=[];
function validEndpoint(p,departure){
 if(p.length<3)return false;const anchor=p[departure?p.length-1:0];let count=0,span=0;
 for(let n=1;n<p.length&&n<=8;n++){
  const a=p[departure?p.length-n-1:n-1],b=p[departure?p.length-n:n],dt=b[0]-a[0];
  if(!(dt>0&&dt<=1.5)||Math.max(Math.abs(a[0]-anchor[0]),Math.abs(b[0]-anchor[0]))>3)break;
  span+=dt;count++;
 }
 return count>=2&&span>=.5;
}
function interpolate(p,t){
 let j=1;while(j<p.length-1&&p[j][0]<t)j++;
 const a=p[j-1],b=p[j],u=(t-a[0])/(b[0]-a[0]);return a[1]+u*(b[1]-a[1]);
}
for(const site of snapshot.sites)for(const direction of ['eastbound','westbound'])for(const width of widths){
 const sign=direction==='eastbound'?1:-1,origin=site.station_m*sign;
 const a=[],b=[],ai=[],bi=[],truth=new Map();
 for(const [id,tr] of site.tracks.entries()){
  if(tr.method||tr.direction!==direction||!vehicles.has(String(tr.class_type)))continue;
  const p=tr.points;
  if(p.length<7||p[0][0]<tail[0]||p.at(-1)[0]>tail[1])continue;
  // Keep continuous source tracks so hidden ground truth is actually available.
  if(p.some((v,i)=>i&&(v[0]<=p[i-1][0]||v[0]-p[i-1][0]>1.5||sign*(v[1]-p[i-1][1])<-.3)))continue;
  const pa=p.filter(v=>v[1]*sign<=origin-width/2),pb=p.filter(v=>v[1]*sign>=origin+width/2);
  const left=validEndpoint(pa,true),right=validEndpoint(pb,false);
  const fragment=(points,side)=>({points,direction,class_type:tr.class_type,
   source_key:['anonymous',side+id],movement:{state:'unknown'}});
  if(left){a.push(fragment(pa,'up-'));ai.push(id);}
  if(right){b.push(fragment(pb,'down-'));bi.push(id);}
  if(left&&right){
   const hidden=p.filter(v=>v[0]>pa.at(-1)[0]&&v[0]<pb[0][0]);
   truth.set(id,hidden);
  }
 }
 const up={id:'up',station_m:site.station_m-sign*100,tracks:a};
 const down={id:'down',station_m:site.station_m+sign*100,tracks:b};
 const s={generated_at:1,sites:[up,down]},l={state:'ready',snapshot_generated_at:1,within_intersection:[],between_intersections:[]};
 const inputHash=hash(JSON.stringify(s));
 for(const [name,build] of Object.entries(models)){
  const r=build(s,l),errors=[],usedA=new Set(),usedB=new Set();let correct=0,wrong=0;
  for(const p of r.paths){
   const ix=p.endpoint_provenance.departure.source_fragment_indices[0],iy=p.endpoint_provenance.arrival.source_fragment_indices[0];
   assert.equal(usedA.has(ix),false);assert.equal(usedB.has(iy),false);usedA.add(ix);usedB.add(iy);
   assert.equal(p.kpi_eligible,false);
   assert.deepEqual(p.points[0].slice(0,2),a[ix].points.at(-1).slice(0,2));
   assert.deepEqual(p.points.at(-1).slice(0,2),b[iy].points[0].slice(0,2));
   if(ai[ix]===bi[iy]&&truth.has(ai[ix])){
    correct++;
    if(truth.get(ai[ix]).length)errors.push(mean(truth.get(ai[ix]).map(v=>Math.abs(interpolate(p.points,v[0])-v[1]))));
   }else wrong++;
  }
  assert.equal(hash(JSON.stringify(s)),inputHash);
  rows.push({site:site.id,direction,width_m:width,model:name,departures:a.length,arrivals:b.length,
   eligible:truth.size,correct,wrong,unrecovered:truth.size-correct,predicted:r.paths.length,gap_mae_m:errors});
 }
}
function aggregate(selected){
 const out={eligible:0,predicted:0,correct:0,wrong:0,unrecovered:0},errors=[];
 for(const row of selected){for(const k of Object.keys(out))out[k]+=row[k];errors.push(...row.gap_mae_m);}
 return {...out,precision:out.predicted?out.correct/out.predicted:null,recall:out.eligible?out.correct/out.eligible:null,
  position_evaluated_gaps:errors.length,correct_match_position_mae_m:mean(errors),correct_match_gap_mae_p95_m:quantile(errors,.95)};
}
const totals=Object.fromEntries(Object.keys(models).map(k=>[k,aggregate(rows.filter(r=>r.model===k))]));
const by_width=Object.fromEntries(widths.map(w=>[w,Object.fromEntries(Object.keys(models).map(k=>[k,aggregate(rows.filter(r=>r.model===k&&r.width_m===w))]))]));
const report={snapshot:args.snapshot,snapshot_sha256:hash(bytes),module_sha256:Object.fromEntries(Object.entries(modules).map(([k,p])=>[k,hash(fs.readFileSync(p))])),
 evaluation:'Spatial masks at seven recorded sites, both directions, final 20 minutes of the frozen development hour. Anonymous fragment IDs; hidden points, shapes and full-track movement labels are withheld. One-to-one matching among competing fragments. Each width is a separate trial and may reuse the same vehicle. A matched pair with no interior recorded sample is scored for identity only, not position error. Not an independent recording or a cross-sensor identity test.',
 relative_time_window_s:tail,widths_m:widths,totals,by_width,rows};
if(args.layers){
 const layerFile=JSON.parse(fs.readFileSync(args.layers)),layers=layerFile.layers||layerFile;
 const beforeHash=hash(JSON.stringify([snapshot,layers])),sites=new Map(snapshot.sites.map(s=>[s.id,s]));
 report.recorded_replay={};
 function slope(p,departure){
  const anchor=p[departure?p.length-1:0],v=[];
  for(let n=1;n<p.length&&n<=8;n++){
   const a=p[departure?p.length-n-1:n-1],b=p[departure?p.length-n:n],dt=b[0]-a[0];
   if(!(dt>0&&dt<=1.5)||Math.max(Math.abs(a[0]-anchor[0]),Math.abs(b[0]-anchor[0]))>3)break;
   v.push((b[1]-a[1])/dt);
  }
  return v.sort((a,b)=>a-b)[Math.floor(v.length/2)];
 }
 for(const [name,build] of Object.entries(models)){
  const r=build(snapshot,layers),usedA=new Set(),usedB=new Set();let changed=0,maxError=0,segments=0;
  for(const p of r.paths){
   const sign=p.direction==='eastbound'?1:-1,ref=p.endpoint_provenance;
   for(const [side,used,last] of [['departure',usedA,true],['arrival',usedB,false]]){
    const e=ref[side],index=e.source_fragment_indices[0],id=e.site+'|'+index;
    assert.equal(used.has(id),false);used.add(id);
    const source=sites.get(e.site).tracks[index].points,endpoint=source[last?source.length-1:0],curveEndpoint=p.points[last?0:p.points.length-1];
    assert.deepEqual(curveEndpoint.slice(0,2),endpoint.slice(0,2));
    const error=Math.abs(curveEndpoint[2]-Math.max(0,slope(source,last)*sign));
    if(error>1e-7)changed++;maxError=Math.max(maxError,error);
   }
   assert.equal(p.kpi_eligible,false);
   for(let i=1;i<p.points.length;i++){
    const a=p.points[i-1],b=p.points[i];segments++;
    assert.ok(b[0]>a[0]);assert.ok(sign*(b[1]-a[1])>=-1e-7);assert.ok(b[2]>=0&&b[2]<=35+1e-7);
   }
  }
  assert.equal(hash(JSON.stringify([snapshot,layers])),beforeHash);
  if(name==='after')assert.equal(changed,0);
  report.recorded_replay[name]={method:r.method,connections:r.paths.length,changed_endpoint_slopes:changed,
   maximum_endpoint_speed_change_mps:maxError,checked_segments:segments,links:r.links};
 }
}
fs.mkdirSync(path.dirname(args.out),{recursive:true});fs.writeFileSync(args.out,JSON.stringify(report,null,2));
console.log(JSON.stringify({totals,by_width,recorded_replay:report.recorded_replay&&Object.fromEntries(Object.entries(report.recorded_replay).map(([k,v])=>[k,{...v,links:undefined}]))},null,2));
