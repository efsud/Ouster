const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_EXECUTABLE});
 try{
  const page=await browser.newPage({viewport:{width:1300,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:8768/');
  await page.waitForFunction(()=>document.querySelector('#interactive-status').textContent.includes('2 intersections'));
  assert.equal(await page.locator('#track-sites input').count(),10);
  await page.locator('#tracks-none').click();await page.waitForFunction(()=>document.querySelector('#interactive-status').textContent.includes('Choose one'));
  await page.locator('#track-sites input[value="OBC-AG-SA-C257238"]').check();
  await page.locator('#track-sites input[value="OBC-AG-SA-C251064"]').check();
  await page.locator('#recorded-figure').selectOption('westbound-1793983500.png');
  await page.waitForFunction(()=>/2 intersections · westbound · 11:45:00–11:50:00/.test(document.querySelector('#interactive-status').textContent));
  await page.locator('#interactive-tracks').screenshot({path:'/private/tmp/finch-interactive.png'});
  await page.locator('#tracks-none').click();await page.locator('#track-sites input[value="OBC-AG-SA-C351163"]').check();
  await page.waitForFunction(()=>document.querySelector('#interactive-status').textContent.includes('0 measured fragments'));
  await page.locator('#tracks-all').click();
  await page.waitForFunction(()=>document.querySelector('#interactive-status').textContent.includes('10 intersections'));
  assert.deepEqual(errors,[]);console.log('Passed: pair selection, direction/time, empty selection, missing site, all sites; no JS errors.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
