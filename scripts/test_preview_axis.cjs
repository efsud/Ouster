const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('dashboard/static/app.js','utf8');
const helper=source.slice(source.indexOf('function alignPreviewObject('),source.indexOf('function alignmentLabel('));
const box={};vm.createContext(box);vm.runInContext(helper,box);
for(const angle of [0,89,90,180,268,271]){
 const origin={lat:28.66,lng:-81.38},site={reference_location:origin,preview_mirror_y:true},c=Math.cos(origin.lat*Math.PI/180),t=angle*Math.PI/180;
 const x=.001,y=.002,e=x*Math.cos(t)-y*Math.sin(t),n=x*Math.sin(t)+y*Math.cos(t);
 const object={lng:origin.lng+e/c,lat:origin.lat+n};
 const actual=box.alignPreviewObject(site,object,{state:'approximate',rotation_deg:angle});
 assert.ok(Math.abs(actual.lng-(origin.lng+(x*Math.cos(t)+y*Math.sin(t))/c))<1e-10);
 assert.ok(Math.abs(actual.lat-(origin.lat+x*Math.sin(t)-y*Math.cos(t)))<1e-10);
 assert.equal(box.alignPreviewObject(site,object,{state:'live',rotation_deg:angle}),object);
}
console.log('Display-axis correction equals reflection before rotation; strict calibrated mode unchanged.');
