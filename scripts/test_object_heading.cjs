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
