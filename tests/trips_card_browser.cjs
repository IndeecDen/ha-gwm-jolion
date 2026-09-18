const {chromium}=require('playwright');
const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome',args:['--enable-unsafe-swiftshader']});
 try{
  const page=await browser.newPage({viewport:{width:430,height:1050}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/*',async route=>{
   const url=new URL(route.request().url());
   if(url.hostname==='tiles.openfreemap.org')return route.fulfill({contentType:'application/json',body:JSON.stringify({version:8,sources:{},layers:[{id:'background',type:'background',paint:{'background-color':url.pathname.endsWith('/dark')?'#25313e':'#e9ede8'}}]})});
   if(url.hostname==='tile.openstreetmap.org')return route.fulfill({status:200,contentType:'image/png',body:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=','base64')});
   if(url.pathname.startsWith('/gwm-jolion/')){
    const file=path.resolve('custom_components/gwm_jolion/frontend',url.pathname.slice('/gwm-jolion/'.length));
    return route.fulfill({body:fs.readFileSync(file),contentType:file.endsWith('.css')?'text/css':'application/javascript'});
   }
   return route.fulfill({body:'<style>body{margin:0;background:#18232a;color:#dde6ed;font-family:Arial;--primary-color:#039ecc;--primary-text-color:#dde6ed;--secondary-text-color:#a4b4c0;--secondary-background-color:#28363d}ha-card{display:block;background:#223039}</style><gwm-jolion-trips-card></gwm-jolion-trips-card>'});
  });
  await page.goto('http://gwm.test');
  await page.addScriptTag({path:path.resolve('custom_components/gwm_jolion/frontend/gwm-jolion-trips-card.js')});
  await page.evaluate(()=>{customElements.define('ha-icon',class extends HTMLElement{connectedCallback(){this.textContent=this.getAttribute('icon')==='mdi:counter'?'◉':'▦';}});});
  await page.evaluate(()=>{
   window.calls=[];window.card=document.querySelector('gwm-jolion-trips-card');
   window.sample={km:14.6,method:'odometer',samples:20,timezone:'Europe/Moscow',retention_days:90,last:1789570800,days:[{date:'2026-09-16',km:14.6,method:'odometer',gaps:1}],segments:[[[55.75,37.60],[55.752,37.61],[55.759,37.62]],[[55.763,37.63],[55.768,37.64]]]};
   window.hass={config:{time_zone:'Europe/Moscow'},states:{},callWS:async msg=>{calls.push(msg);return structuredClone(sample);}};
   card.setConfig({entity:'device_tracker.test',title:'Поездки · Jolion'});card.hass=hass;
  });
  await page.waitForFunction(()=>card._map && card._layer.getLayers().length===4);
  await page.waitForFunction(()=>card._base.getMaplibreMap?.().isStyleLoaded());
  assert.equal(await page.evaluate(()=>card._baseStyle),'positron');
  for(const style of ['dark','liberty','osm','positron']){
   await page.evaluate(style=>card.setConfig({...card._config,map_style:style}),style);
   await page.waitForFunction(style=>card._baseStyle===style && card._layer.getLayers().length===4,style);
  }
  await page.evaluate(()=>{
   window.originalMap=GwmTripsMapLibre.Map;
   GwmTripsMapLibre.Map=class {constructor(){throw Error('WebGL unavailable');}};
   card.setConfig({...card._config,map_style:'dark'});
  });
  await page.waitForFunction(()=>card.shadowRoot.querySelector('.map-status').textContent.includes('Показана OpenStreetMap'));
  assert.equal(await page.evaluate(()=>card._layer.getLayers().length),4);
  await page.evaluate(()=>{GwmTripsMapLibre.Map=originalMap;card.setConfig({...card._config,map_style:'positron'});});
  await page.waitForFunction(()=>card._base.getMaplibreMap?.().isStyleLoaded());
  assert.match(await page.locator('.km').textContent(),/14,6/);
  await page.evaluate(async()=>{
   sample.gaps=[[[55.759,37.62],[55.763,37.63]]];
   await card._load();
  });
  assert.equal(await page.evaluate(()=>card._layer.getLayers().filter(layer=>layer.options.dashArray==='5 7').length),1);
  assert.match(await page.locator('.km').textContent(),/14,6/);
  await page.evaluate(()=>{
   window.failedBase=card._base;
   card._base.getMaplibreMap().fire('error',{error:Error('Network offline')});
  });
  assert.equal(await page.evaluate(()=>card._baseNeedsRetry),true);
  await page.evaluate(()=>card._load());
  await page.waitForFunction(()=>card._base!==failedBase && card._base.getMaplibreMap?.().isStyleLoaded());
  assert.equal(await page.evaluate(()=>card._layer.getLayers().length),5);
  await page.locator('[data-mode="yesterday"]').click();
  await page.waitForFunction(()=>document.querySelector('gwm-jolion-trips-card').shadowRoot.querySelector('[data-mode="yesterday"]').classList.contains('active'));
  assert.equal(await page.locator('.dates').isVisible(),false);
  assert.equal(await page.locator('h2,details,.notice,.coverage').count(),0);
  assert(await page.locator('.map').evaluate(el=>el.getBoundingClientRect().bottom) <= await page.locator('.summary').evaluate(el=>el.getBoundingClientRect().top));
  await page.locator('#calendar').click();
  await page.locator('#start').fill('2026-09-01');await page.locator('#end').fill('2026-09-16');await page.locator('#show').click();
  await page.waitForFunction(()=>calls.at(-1).start==='2026-09-01' && calls.at(-1).end==='2026-09-16');
  assert.equal(await page.locator('.dates').isVisible(),false);
  assert.match(await page.locator('#calendar').getAttribute('class'),/active/);
  await page.screenshot({path:path.join(process.env.TEMP,'gwm-trips-card.png'),fullPage:true});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  await page.evaluate(()=>{sample={...sample,samples:0,days:[],segments:[],gaps:[],last:null};card._load();});
  await page.waitForFunction(()=>card.shadowRoot.querySelector('.error').textContent.includes('нет записей'));
  assert.equal(await page.evaluate(()=>card._layer.getLayers().length),0);
  await page.evaluate(()=>{hass.callWS=async()=>{throw Error('Нет доступа');};card._load();});
  await page.waitForFunction(()=>card.shadowRoot.querySelector('.error').textContent==='Нет доступа');
  await page.evaluate(()=>{window.saved=card;card.remove();});
  assert.equal(await page.evaluate(()=>saved._map),null);
  assert.deepEqual(errors,[]);
  console.log('Trips card: route, calendar, mobile layout, empty history and errors passed');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
