const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict');
(async()=>{const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_EXECUTABLE});try{
 const page=await browser.newPage({viewport:{width:1300,height:1100}}),errors=[];page.on('pageerror',e=>errors.push(e.message));await page.goto('http://127.0.0.1:8768/');
 await page.waitForFunction(()=>document.querySelector('#interactive-status').textContent.includes('2 intersections'));
 await page.locator('#show-virtual').check();
 await page.waitForFunction(()=>document.querySelector('#virtual-status').textContent.includes('10 dashed virtual paths'));
 await page.locator('#recorded-figure').selectOption('eastbound-1793986500.png');
 await page.waitForFunction(()=>document.querySelector('#interactive-status').textContent.includes('12:35:00'));
 await page.locator('#interactive-tracks').screenshot({path:'/private/tmp/finch-virtual.png'});
 await page.locator('#object-filter').selectOption('2');await page.waitForFunction(()=>document.querySelector('#virtual-status').textContent.includes('Virtual paths hidden'));
 assert.match(await page.locator('#object-filter option[value="2"]').textContent(),/Car/);
 await page.locator('#object-filter').selectOption('all');
 await page.waitForFunction(()=>!document.querySelector('#interactive-status').textContent.includes('Loading'));
 await page.locator('#object-filter').selectOption('vehicles');
 await page.locator('#recorded-figure').selectOption('eastbound-1793983500.png');
 await page.waitForFunction(()=>document.querySelector('#virtual-status').textContent.includes('0 dashed virtual paths'));
 assert.deepEqual(errors,[]);console.log('Passed virtual overlay, held-out-only window, class selection and pooled-vehicle restriction.');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exit(1);});
