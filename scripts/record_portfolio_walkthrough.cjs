// Actual dashboard screen recordings. Caption/title composition is performed
// separately; no sensor settings, production assets or observations are changed.
const fs=require('node:fs'),path=require('node:path'),{performance}=require('node:perf_hooks');
const root=path.resolve(__dirname,'..');process.chdir(root);
const runtime=process.env.CODEX_NODE_MODULES||'/Users/fatemehsadeghi/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules';
process.env.PLAYWRIGHT_BROWSERS_PATH=path.join(root,'data/portfolio/browser-cache');
const {chromium}=require(path.join(runtime,'playwright'));
const base=process.env.PORTFOLIO_BASE_URL||'http://127.0.0.1:8775';
const folder=path.join(root,'data/portfolio'),examples=JSON.parse(fs.readFileSync(path.join(root,'docs/portfolio/Portfolio_Recording_Evidence.json')));
const evidence={recorded_at:new Date().toISOString(),capture_id:examples.capture_id,clips:[],errors:[]};
let browser;
async function capture(name,url,duration,prepare,actions){
 const context=await browser.newContext({viewport:{width:1600,height:760},deviceScaleFactor:1,recordVideo:{dir:path.join(folder,'clips'),size:{width:1600,height:760}}});
 const page=await context.newPage();page.on('pageerror',e=>evidence.errors.push({clip:name,error:e.message}));
 let started;
 try{
  await page.goto(url);await prepare(page);
  await page.evaluate(()=>{const e=document.createElement('div');e.id='portfolio-pointer';e.style.cssText='position:fixed;z-index:99999;width:18px;height:18px;border:2px solid white;border-radius:50%;background:#168d8099;box-shadow:0 0 0 5px #159e8833,0 2px 6px #1238;pointer-events:none;left:-50px;top:-50px;transform:translate(-50%,-50%)';document.body.append(e);});
  started=performance.now();
  const wait=async t=>{const ms=t*1000-(performance.now()-started);if(ms>0)await page.waitForTimeout(ms);};
  const move=async(x,y)=>{await page.mouse.move(x,y,{steps:12});await page.locator('#portfolio-pointer').evaluate((e,p)=>{e.style.left=p.x+'px';e.style.top=p.y+'px';},{x,y});};
  const point=async loc=>{const b=await loc.boundingBox();if(!b)throw Error('Missing target');await move(b.x+b.width/2,b.y+b.height/2);};
  const click=async loc=>{await point(loc);await loc.click();await page.waitForTimeout(160);};
  const select=async(loc,value)=>{await point(loc);await loc.selectOption(value);};
  const snap=async label=>{await page.screenshot({path:path.join(folder,'qa',name+'-'+label+'.png')});console.log(JSON.stringify({clip:name,scene:label,time:(performance.now()-started)/1000}));};
  await actions({page,wait,move,point,click,select,snap});await wait(duration);
  const elapsed=(performance.now()-started)/1000;
  const video=await page.video().path();evidence.clips.push({name,path:video,duration:elapsed,target_duration:duration});
 }finally{await context.close();fs.writeFileSync(path.join(folder,'capture-log.json'),JSON.stringify(evidence,null,2));}
}
(async()=>{
 browser=await chromium.launch({headless:true,executablePath:process.env.PORTFOLIO_CHROME||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
 try{
 await capture('live',base+'/?region=Florida#map',32,async page=>{
  await page.locator('#sites-list .site').first().waitFor();await page.waitForTimeout(4000);
 },async({page,wait,point,click,select,snap})=>{
  await snap('overview');await point(page.locator('#region'));await wait(4);await select(page.locator('#region'),'Toronto');
  await wait(7);await select(page.locator('#region'),'Florida');await wait(9);await click(page.locator('[data-site-id="OBC-AG-SA-C257225"]'));
  await wait(11);await click(page.locator('.leaflet-control-zoom-in'));await wait(17);await snap('moving-objects');
  evidence.live=await page.evaluate(()=>({objects:document.getElementById('object-count').textContent,phases:document.getElementById('live-phase-cards').innerText}));
  await wait(23);await point(page.locator('#live-phase-cards'));await page.locator('#live-phase-panel').evaluate(e=>e.style.boxShadow='inset 0 0 0 2px #179b88');
  await wait(27);await snap('phases');
 });
 await capture('history',base+'/florida_rolling.html?embed=workspace&frozen='+examples.capture_id+'&between=1',58,async page=>{
  await page.waitForFunction(()=>typeof reconstruction!=='undefined'&&reconstruction?.within_intersection?.length&&data?.sites?.length,null,{timeout:60000});
  await page.locator('#color-layer').uncheck();await page.locator('#uncertain-layer').uncheck();
 },async({page,wait,move,point,click,select,snap})=>{
  await snap('full-hour');await wait(3);await select(page.locator('#direction'),'westbound');await wait(6);await select(page.locator('#direction'),'eastbound');
  await select(page.locator('#objects'),'all');await wait(9);await select(page.locator('#objects'),'vehicles');await wait(11);
  for(const id of ['OBC-AG-SA-C257222','OBC-AG-SA-C257223','OBC-AG-SA-C251068','OBC-AG-SA-C257236','OBC-AG-SA-C257227'])await click(page.locator('#sites input[value="'+id+'"]'));
  await wait(14);const b=await page.locator('#plot').boundingBox();await move(b.x+b.width*.78,b.y+b.height*.5);
  for(let i=0;i<13;i++){await page.mouse.wheel(0,-100);await page.waitForTimeout(160);}
  await wait(20);await snap('pointer-zoom');await wait(21);
  const prepareExample=async(p,ids)=>page.evaluate(({p,ids})=>{for(const box of document.querySelectorAll('#sites input'))box.checked=ids.includes(box.value);document.getElementById('direction').value=p.direction;for(const id of ['within-layer','between-layer','color-layer','uncertain-layer'])document.getElementById(id).checked=false;view=[data.start+p.points[0][0]-14,data.start+p.points.at(-1)[0]+20];draw();},{p,ids});
  await prepareExample(examples.within,[examples.within.site]);await point(page.locator('#within-layer'));await snap('local-before');await wait(25);await click(page.locator('#within-layer'));await wait(28);await snap('local-after');
  await wait(31);await prepareExample(examples.between,examples.between.sites);await point(page.locator('#between-layer'));await snap('between-before');await wait(36);await click(page.locator('#between-layer'));await wait(40);await snap('between-after');
  await wait(44);await click(page.locator('#uncertain-layer'));await wait(48);await snap('uncertain');
  await wait(51);await page.evaluate(()=>{for(const box of document.querySelectorAll('#sites input'))box.checked=true;document.getElementById('uncertain-layer').checked=false;document.getElementById('within-layer').checked=true;view=[data.start+2680,data.start+2810];draw();});await snap('corridor');
  evidence.history=await page.evaluate(()=>({source:document.getElementById('message').textContent,counts:document.getElementById('layer-counts').textContent}));
 });
 await capture('ctm',base+'/?region=Florida#map',16,async page=>{
  await page.locator('#sites-list .site').first().waitFor();await page.locator('.brand').click();await page.locator('[data-tab="ctm"]').click();
  await page.waitForFunction(()=>document.getElementById('heatmap').children.length>0);await page.waitForTimeout(500);
 },async({page,wait,point,click,snap})=>{
  await snap('default');await wait(5);await point(page.locator('#green'));await page.locator('#green').focus();await page.locator('#green').press('Home');for(let i=0;i<6;i++)await page.locator('#green').press('ArrowRight');await click(page.locator('#run-ctm'));
  await wait(10);await snap('scenario');
 });
 }finally{await browser.close();fs.writeFileSync(path.join(folder,'capture-log.json'),JSON.stringify(evidence,null,2));}
 console.log(JSON.stringify({complete:true,clips:evidence.clips,errors:evidence.errors}));
})().catch(e=>{console.error(e.stack);process.exitCode=1;});
