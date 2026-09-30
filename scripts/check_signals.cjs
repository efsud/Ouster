const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict');
(async()=>{const b=await chromium.launch({headless:true,executablePath:process.env.CHROME_EXECUTABLE});try{
 const page=await b.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:8765/?site=OBC-AG-SA-C618861');
 await page.waitForFunction(()=>document.querySelectorAll('#signal-phases .signal-state').length>0,{},{timeout:30000});
 assert.match(await page.locator('#signal-title').textContent(),/Driftwood/);
 assert.match(await page.locator('#signal-status').textContent(),/snapshot/i);
 console.log('Signal UI:',await page.locator('#signal-phases .signal-state').count(),'phase reports');
 await page.locator('[data-site-id="OBC-AG-SA-C618857"]').click();
 await page.waitForFunction(()=>document.querySelector('#signal-title').textContent.includes('Norfinch'));
 assert.equal(await page.locator('#signal-phases .signal-state').count(),0);
 assert.deepEqual(errors,[]);console.log('Site isolation and JavaScript error checks passed.');
 }finally{await b.close();}})().catch(e=>{console.error(e);process.exit(1)});
