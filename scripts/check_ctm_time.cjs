const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_EXECUTABLE});
 try{
  const page=await browser.newPage({timezoneId:'America/Toronto',locale:'en-CA'});
  await page.goto('http://127.0.0.1:8765/');
  await page.waitForFunction(()=>Object.keys(state.metrics).length>0);
  for(const [start,end] of [['2026-09-29T15:17','2026-09-29T16:17'],['2026-09-29T23:30','2026-09-30T00:30'],['2026-11-01T00:30','2026-11-01T02:30']]){
   const r=await page.evaluate(({start,end})=>{
    const a=new Date(start).getTime()/1000,b=new Date(end).getTime()/1000;
    const rows=[{start:a,end:a+300,values:{volume:10},approach:'test',quality:{status:'test'}},{start:b-300,end:b,values:{volume:20},approach:'test',quality:{status:'test'}}];
    const node=document.createElement('div');node.innerHTML=lineChart(rows,'volume',state.metrics,{start:a,end:b,local:true});
    return {start:+node.querySelector('svg').dataset.start,end:+node.querySelector('svg').dataset.end,a,b,ticks:[...node.querySelectorAll('.time-tick')].map(e=>e.textContent),expected:[localChartTime(a),localChartTime(b)],tooltip:node.querySelector('title').textContent};
   },{start,end});
   assert.equal(r.start,r.a);assert.equal(r.end,r.b);
   assert.equal(r.ticks[0],r.expected[0]);assert.equal(r.ticks.at(-1),r.expected[1]);
   assert.ok(r.tooltip.includes(r.expected[0]));
   if(start.includes('11-01')){assert.match(r.ticks[0],/EDT/);assert.match(r.ticks.at(-1),/EST/);}
  }
  console.log('CTM time axis: selected bounds, local labels, midnight and daylight-saving transition passed.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
