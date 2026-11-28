const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.CHROME_EXECUTABLE?{executablePath:process.env.CHROME_EXECUTABLE}:{})});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:8765/');
  await page.locator('[data-site-id="OBC-AG-SA-C618861"]').click();
  await page.waitForFunction(()=>movingObjects.size>0,{},{timeout:30000});
  const first=await page.evaluate(()=>Array.from(movingObjects,([k,m])=>[k,m.marker.getLatLng().lat,m.marker.getLatLng().lng]));
  await page.waitForTimeout(1500);
  const next=await page.evaluate(()=>Array.from(movingObjects,([k,m])=>[k,m.marker.getLatLng().lat,m.marker.getLatLng().lng]));
  const changed=next.filter(b=>first.some(a=>a[0]===b[0]&&(a[1]!==b[1]||a[2]!==b[2]))).length;
  assert.ok(changed>0,'At least one persistent real object must move');
  fs.mkdirSync('data/qa',{recursive:true});await page.screenshot({path:'data/qa/toronto-live-animation.png',fullPage:true});
  await page.locator('#approximate-objects').uncheck();
  await page.waitForFunction(()=>movingObjects.size===0);
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({visibleObjects:next.length,persistentObjectsMoved:changed,strictModeClearsApproximate:true,jsErrors:errors.length}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
