// UI smoke test. Install Playwright separately or set PLAYWRIGHT_MODULE to its path.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
(async () => {
  const browser = await chromium.launch({headless:true,...(process.env.CHROME_EXECUTABLE?{executablePath:process.env.CHROME_EXECUTABLE}:{})});
  try {
    const page = await browser.newPage({viewport:{width:1440,height:1000}});
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.goto('http://127.0.0.1:8765');
    await page.waitForSelector('.leaflet-container');
    await page.locator('#region').selectOption('Florida');
    assert.equal(await page.locator('.site').count(),7);
    await page.locator('.site').first().click();
    await page.waitForFunction(()=>document.getElementById('site-state').textContent==='unavailable');
    fs.mkdirSync('data/qa',{recursive:true});
    await page.screenshot({path:'data/qa/live-desktop.png',fullPage:true});
    await page.locator('[data-tab=history]').click();
    await page.locator('#load-demo').click();
    await page.waitForFunction(()=>document.getElementById('window-count').textContent==='36 windows');
    assert.equal(await page.locator('.kpi-card').count(),7);
    assert.equal(await page.locator('#quality-rows tr').count(),36);
    await page.locator('.kpi-card').nth(3).click();
    assert.match(await page.locator('#chart-title').textContent(),/Arrivals on green/);
    await page.screenshot({path:'data/qa/history-desktop.png',fullPage:true});
    const downloaded = page.waitForEvent('download');await page.locator('#export').click();
    const download=await downloaded;assert.equal(download.suggestedFilename(),'ouster-kpis.csv');
    await page.locator('[data-tab=ctm]').click();
    await page.waitForSelector('#heatmap svg');
    await page.locator('#green').fill('0');await page.locator('#run-ctm').click();
    await page.waitForFunction(()=>document.querySelector('#ctm-stats strong')?.textContent==='0');
    await page.locator('#green').fill('45');await page.locator('#run-ctm').click();
    await page.waitForFunction(()=>document.querySelector('#ctm-stats strong')?.textContent!=='0');
    await page.screenshot({path:'data/qa/ctm-desktop.png',fullPage:true});
    await page.locator('[data-tab=optimization]').click();
    assert.match(await page.locator('#optimization').textContent(),/Awaiting model development/);
    await page.setViewportSize({width:390,height:844});
    await page.locator('[data-tab=live]').click();
    await page.screenshot({path:'data/qa/live-mobile.png',fullPage:true});
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),'Mobile horizontal overflow');
    // Browser-only synthetic stream responses exercise network mapping; no field data is saved.
    await page.route('**/api/network-live?*',route=>route.fulfill({json:{snapshots:[
      {site:'OBC-AG-SA-C251068',state:'live',timestamp:Date.now()/1000,objects:[{id:'fixture-a',lat:28.661,lng:-81.386,class:'2'}]},
      {site:'OBC-AG-SA-C257206',state:'live',timestamp:Date.now()/1000,objects:[{id:'fixture-b',lat:28.6611,lng:-81.3861,class:'10'}]},
      {site:'OBC-AG-SA-C257222',state:'stale',objects:[]}
    ]}}));
    await page.evaluate(()=>map.setView([28.661,-81.386],18,{animate:false}));
    await page.waitForFunction(()=>document.getElementById('object-count').textContent==='2');
    assert.match(await page.locator('#connection').textContent(),/2 \/ 3 sites live/);
    await page.evaluate(()=>map.setView([43.6532,-79.3832],18,{animate:false}));
    await page.waitForFunction(()=>document.getElementById('object-count').textContent==='0');
    assert.deepEqual(errors,[]);
    console.log('PASS: map inventory, stale/empty state, demo history, KPI selection, CSV export, CTM red/green, optimization placeholder, mobile fit, multiple live sites and viewport filtering, no JS errors.');
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
