const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_EXECUTABLE});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:8765/?site=OBC-AG-SA-C618861');
  await page.waitForFunction(()=>document.querySelector('#history-site option[value="OBC-AG-SA-C618861"]'));
  await page.locator('[data-tab=history]').click();
  await page.locator('#history-site').selectOption('OBC-AG-SA-C618861');
  await page.locator('#hctm-latest').click();
  await page.waitForFunction(()=>document.querySelector('#from').value!=='' && document.querySelector('#to').value!=='');
  await page.locator('#hctm-run').click();
  await page.waitForFunction(()=>document.querySelector('#hctm-status').textContent.includes('saved locally'),{},{timeout:60000});
  assert.equal(await page.locator('#hctm-rows tr').count(),12);
  assert.equal(await page.locator('#hctm-chart svg').count(),1);
  await page.locator('#hctm-kpi').selectOption('queue_p95');
  assert.equal(await page.locator('#hctm-rows tr').count(),0);
  await page.locator('#hctm-run').click();
  await page.waitForFunction(()=>document.querySelector('#hctm-status').textContent.includes('saved locally'),{},{timeout:60000});
  assert.match(await page.locator('#hctm-title').textContent(),/queue P95/);
  assert.equal(await page.locator('#hctm-kpi option[value=aog]').evaluate(el=>el.disabled),true);
  assert.equal(await page.locator('#history-advanced').getAttribute('open'),null);
  const download=page.waitForEvent('download');await page.locator('#hctm-download').click();
  assert.match((await download).suggestedFilename(),/^ctm-.*\.json$/);
  await page.screenshot({path:'data/qa/historical-ctm.png',fullPage:true});
  await page.setViewportSize({width:390,height:844});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),true);
  await page.locator('#history-site').selectOption('OBC-AG-SA-C618857');
  assert.equal(await page.locator('#hctm-rows tr').count(),0);
  assert.deepEqual(errors,[]);
  console.log('Historical CTM: real recording, 12 windows, KPI selection, missing metrics, JSON download, mobile and selection reset passed.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
