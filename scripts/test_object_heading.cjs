const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const s=fs.readFileSync('dashboard/static/app.js','utf8'),box={};vm.createContext(box);
vm.runInContext(s.slice(s.indexOf('function movementHeading('),s.indexOf('for(const [kind,style]')),box);
vm.runInContext(s.slice(s.indexOf('function alignPreviewObject('),s.indexOf('function alignmentLabel(')),box);
const el={style:{}},m={heading:80,isMoving:false,headingAnchor:[43,-79],marker:{getElement:()=>({querySelector:()=>el})}};
box.updateObjectHeading(m,[43.000005,-79],{heading_deg:150,speed_mps:.1});assert.equal(m.heading,80);
box.updateObjectHeading(m,[43.00001,-79],{heading_deg:100,speed_mps:2});assert.equal(m.heading,100);
box.updateObjectHeading(m,[43.000011,-79],{heading_deg:160,speed_mps:.3});assert.equal(m.heading,100);
m.heading=null;box.updateObjectHeading(m,[43,-79],{heading_deg:275,speed_mps:0});assert.equal(m.heading,275);
for(const theta of [89,90,140,268,271]){
 const rot=.8,rawBearing=90+rot*180/Math.PI-theta;
 const o=box.alignPreviewObject({preview_mirror_y:true,reference_location:{lat:43,lng:-79}},{lat:43,lng:-79,heading_deg:rawBearing},{state:'approximate',rotation_deg:theta});
 const expected=((90-rot*180/Math.PI-theta)%360+360)%360;
 assert(Math.abs(o.heading_deg-expected)<1e-9);
}
console.log('First-frame heading, stopped jitter, restart movement and mirrored heading checks passed.');
const geometry={S:{origin:{lat:0,lng:0},segments:[{a:[0,30],b:[0,150],oneway:1}]}};
const car={kind:'vehicle',lat:60/111320,lng:2/111320,heading_deg:15};
assert.equal(box.roadDisplayHeading('S',car,geometry).heading_deg,0);
for(const changed of [{heading_deg:180},{lat:10/111320},{lng:30/111320},{kind:'pedestrian'}]){
 const input={...car,...changed};assert.equal(box.roadDisplayHeading('S',input,geometry),input);
}
const crossing={S:{...geometry.S,segments:[...geometry.S.segments,{a:[-25,30],b:[75,130],oneway:1}]}};
const ambiguous={...car,heading_deg:22};assert.equal(box.roadDisplayHeading('S',ambiguous,crossing),ambiguous);
console.log('Road heading correction preserves turns, off-road objects, opposing traffic and ambiguous roads.');
