const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_EXECUTABLE});
 try{
  const page=await browser.newPage({viewport:{width:1280,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:8768/');
  await page.waitForFunction(()=>document.querySelector('#recorded-figure-image').naturalWidth>0);
  assert.equal(await page.locator('#recorded-figure option').count(),26);
  await page.locator('#recorded-figure').selectOption({index:14});
  await page.waitForFunction(()=>document.querySelector('#recorded-figure-image').complete&&document.querySelector('#recorded-figure-image').naturalWidth>0);
  await page.locator('#recorded-figure-image').screenshot({path:'data/deepctm/qa-recorded-figure.png'});
  assert.deepEqual(errors,[]);console.log('26 figures available; image rendering and westbound selection passed');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
