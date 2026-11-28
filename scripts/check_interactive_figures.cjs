const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_EXECUTABLE});
 try{
  const page=await browser.newPage({viewport:{width:1300,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:8768/');
  await page.waitForFunction(()=>document.querySelector('#interactive-status').textContent.includes('2 intersections'));
  assert.equal(await page.locator('#track-sites input').count(),10);
  const span=()=>page.locator('#interactive-tracks').evaluate(c=>Number(c.dataset.end)-Number(c.dataset.start));
  assert.equal(await span(),3600);
  await page.locator('#zoom-in').click();assert.equal(await span(),1800);
  await page.locator('#zoom-in').click();assert.equal(await span(),900);
  await page.locator('#time-position').fill('1200');await page.locator('#time-position').dispatchEvent('input');
  await page.waitForFunction(()=>document.querySelector('#interactive-tracks').dataset.start && !document.querySelector('#interactive-status').textContent.includes('Loading'));
  assert.equal(await span(),900);
  const savedStart=await page.locator('#interactive-tracks').getAttribute('data-start');
  await page.locator('#track-sites input[value="OBC-AG-SA-C257238"]').check();
  await page.waitForFunction(()=>document.querySelector('#interactive-status').textContent.includes('3 intersections'));
  assert.equal(await page.locator('#interactive-tracks').getAttribute('data-start'),savedStart);
  await page.locator('#zoom-out').click();assert.equal(await span(),1800);
  await page.locator('#time-reset').click();assert.equal(await span(),3600);
  await page.locator('#interactive-tracks').hover();await page.mouse.wheel(0,-100);
  await page.waitForFunction(()=>Number(document.querySelector('#interactive-tracks').dataset.end)-Number(document.querySelector('#interactive-tracks').dataset.start)<3600);
  await page.locator('#interactive-tracks').dblclick();assert.equal(await span(),3600);

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
