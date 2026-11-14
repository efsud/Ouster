const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_EXECUTABLE});
 try{
  const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:8768/');await page.waitForFunction(()=>document.querySelectorAll('#capture-sensors tr').length===10);
  assert.match(await page.locator('#experiment-title').textContent(),/ten intersections/);
  assert.match(await page.locator('#recorded-figure-status').textContent(),/Figures will appear/);
  assert.deepEqual(errors,[]);console.log('Ten-sensor capture status and pending-figure display passed');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
