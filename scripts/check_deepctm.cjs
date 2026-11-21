const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_EXECUTABLE});
 try{
  const page=await browser.newPage({viewport:{width:1280,height:900}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));await page.goto('http://127.0.0.1:8768/');
  await page.waitForFunction(()=>document.querySelectorAll('#capture-sensors tr').length===2);
  assert.match(await page.locator('#capture-status').textContent(),/recording/);
  assert.match(await page.locator('#forecast-status').textContent(),/No trained results yet/);
  await page.locator('#forecast-direction').selectOption('westbound');
  await page.screenshot({path:'data/deepctm/qa-desktop.png',fullPage:true});
  await page.setViewportSize({width:390,height:844});await page.waitForTimeout(300);
  await page.screenshot({path:'data/deepctm/qa-mobile.png',fullPage:true});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  const fixture={state:'trained_provisional',sequences:{train:50,validation:12,test:12},best_epoch:1,mmce_mean_all_cells_vehicles:2,metrics:{15:{rmse_veh_h:10},60:{rmse_veh_h:20}},persistence:{15:{rmse_veh_h:11},60:{rmse_veh_h:22}},pure_ctm:{15:{rmse_veh_h:15},60:{rmse_veh_h:25}},held_out_forecasts:[0,900].flatMap(t=>[0,2].map(node=>({lead_minutes:15,node,target_start:t,observed_flow:100+t/100,predicted_flow:110+t/100})))};
  await page.route('**/api/deepctm',route=>route.fulfill({json:{state:'software_test_fixture',sensors:[],report:{directions:{eastbound:fixture,westbound:fixture}},assumptions:['Synthetic UI test only']}}));
  await page.reload();await page.waitForFunction(()=>document.querySelectorAll('#forecast-chart path').length===2);
  assert.equal(await page.locator('#forecast-metrics tr').count(),3);
  await page.setViewportSize({width:1280,height:900});await page.waitForTimeout(300);
  await page.screenshot({path:'data/deepctm/qa-synthetic-result.png',fullPage:true});
  assert.deepEqual(errors,[]);console.log('DeepCTM desktop/mobile status and missing-results checks passed');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
