const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict');
(async()=>{const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_EXECUTABLE});try{
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:8765/?site=OBC-AG-SA-C618861');
 await page.waitForFunction(()=>mapSignalStates.size===10,{},{timeout:60000});
 assert.equal(await page.locator('.map-signal-marker').count(),10);
 const checks=await page.evaluate(()=>{
  const phases=['RED','YELLOW','GREEN','UNCONFIRMED'].map((status,i)=>({phase:String(i+1),status:status==='UNCONFIRMED'?'GREEN':status,display_status:status}));
  map.setZoom(18,{animate:false});
  const div=document.createElement('div');div.innerHTML=signalMapIcon({phases}).options.html;
  const colors=['red','yellow','green'].every(c=>div.querySelector('.traffic-lamp.'+c+'.lit'))&&div.querySelectorAll('.traffic-signal').length===4&&div.querySelectorAll('.traffic-lamp.lit').length===3;
  const id='OBC-AG-SA-C618861';mapSignalStates.set(id,{at:Date.now()-6000,result:{phases}});renderMapSignals();
  const html=signalMarkers.get(id).getElement();
  return {colors,stale:html.querySelectorAll('.traffic-signal.unconfirmed').length===4&&html.querySelectorAll('.traffic-lamp.lit').length===0};
 });assert.equal(checks.colors,true);assert.equal(checks.stale,true);
 await page.locator('#region').selectOption('Florida');
 await page.waitForFunction(()=>signalMarkers.size===state.sites.filter(s=>s.region==='Florida'&&(s.calibration_status?.valid||s.reference_location)).length);
 assert.equal(await page.evaluate(()=>[...signalMarkers.keys()].every(id=>state.sites.some(s=>s.id===id&&s.region==='Florida'))),true);
 assert.deepEqual(errors,[]);console.log('Signal map: 10 Toronto markers, phase colours, stale greying, and network switching passed.');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exit(1)});
