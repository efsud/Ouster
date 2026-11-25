const test=require('node:test');
const assert=require('node:assert/strict');
const {build}=require('../static/uncertain-connections.js');

function track(t,x,departure,{id='1',direction='eastbound',v=10,movement,class_type='2'}={}){
 const sign=direction==='eastbound'?1:-1;
 return {source_key:['session',id,class_type],class_type,direction,
  movement:movement||{state:'classified',can_match_next:true,can_match_previous:true,incoming_direction:direction,outgoing_direction:direction},
  points:[0,1,2].map(i=>{const d=departure?i-2:i;return [t+d,x+d*v*sign,v];})};
}
function fixture(){return {generated_at:100,start:0,end:3600,sites:[
 {id:'A',station_m:0,tracks:[track(10,100,true)]},
 {id:'B',station_m:200,tracks:[track(15,150,false)]}]};}
const layers=()=>({state:'ready',snapshot_generated_at:100,within_intersection:[],between_intersections:[]});

test('additional lines join observed endpoints, remain display-only, and do not mutate inputs',()=>{
 const s=fixture(),l=layers(),before=JSON.stringify([s,l]),r=build(s,l);
 assert.equal(r.paths.length,1);const p=r.paths[0];
 assert.equal(p.kpi_eligible,false);assert.equal(p.identity,'unverified_best_guess');assert.equal(p.speed_available,false);
 assert.deepEqual(p.points[0].slice(0,2),[10,100]);assert.deepEqual(p.points.at(-1).slice(0,2),[15,150]);
 assert.equal(JSON.stringify([s,l]),before);
});
test('ties are drawn deterministically, with no reused arrivals or departures',()=>{
 const s=fixture();s.sites[0].tracks.push(track(10,100,true,{id:'2'}));
 const a=build(s,layers()),b=build(s,layers());assert.deepEqual(a,b);assert.equal(a.paths.length,1);
});
test('existing accepted and experimental endpoints cannot be reused',()=>{
 const s=fixture();
 for(const container of ['baseline','residual_color','trajectory_groups']){
  const l=layers(),path={sites:['A','B'],points:[[10,100,10],[15,150,10]]};
  if(container==='baseline')l.between_intersections=[path];else l[container]={between_intersections:[path]};
  assert.equal(build(s,l).paths.length,0);
 }
});
test('internal endpoints of same-site bridges stay reserved',()=>{
 const s=fixture(),l=layers();l.within_intersection=[{site:'A',points:[[10,100,10],[12,120,10]]}];
 assert.equal(build(s,l).paths.length,0);
});
test('known corridor exits are excluded, but unknown movement can be an uncertain proposal',()=>{
 const s=fixture();s.sites[0].tracks[0].movement.can_match_next=false;
 assert.equal(build(s,layers()).paths.length,0);
 s.sites[0].tracks[0].movement={state:'unknown',can_match_next:false};
 assert.equal(build(s,layers()).paths.length,1);
});
test('rejects reverse time, overlap/backtracking, excessive travel speed and stale layers',()=>{
 for(const [t,x] of [[9,150],[15,90],[10.1,150],[200,150]]){
  const s=fixture();s.sites[1].tracks=[track(t,x,false)];assert.equal(build(s,layers()).paths.length,0);
 }
 const l=layers();l.snapshot_generated_at=99;assert.equal(build(fixture(),l).paths.length,0);
});
test('westbound paths decrease in station and match only adjacent intersections',()=>{
 const s=fixture();s.sites[0].tracks=[track(15,100,false,{direction:'westbound'})];
 s.sites[1].tracks=[track(10,150,true,{direction:'westbound'})];
 const r=build(s,layers());assert.equal(r.paths.length,1);assert.deepEqual(r.paths[0].sites,['B','A']);
 for(let i=1;i<r.paths[0].points.length;i++)assert.ok(r.paths[0].points[i][1]<=r.paths[0].points[i-1][1]);
 s.sites.splice(1,0,{id:'middle',station_m:100,tracks:[]});assert.equal(build(s,layers()).paths.length,0);
});
test('vehicle class changes and stopped endpoints can be proposed; pedestrian links are excluded',()=>{
 const s=fixture();s.sites[0].tracks=[track(10,100,true,{v:0})];
 s.sites[1].tracks=[track(25,150,false,{class_type:'4'})];assert.equal(build(s,layers()).paths.length,1);
 s.sites[1].tracks[0].class_type='0';assert.equal(build(s,layers()).paths.length,0);
});
