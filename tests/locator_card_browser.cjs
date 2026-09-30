const {chromium}=require('playwright');
const fs=require('fs'),path=require('path'),assert=require('assert');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:430,height:850}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/*',route=>{
   const url=new URL(route.request().url());
   if(url.pathname.startsWith('/gwm-jolion/')){const file=path.resolve('custom_components/gwm_jolion/frontend',url.pathname.slice('/gwm-jolion/'.length));return route.fulfill({body:fs.readFileSync(file),contentType:file.endsWith('.css')?'text/css; charset=utf-8':'application/javascript; charset=utf-8'});}
   if(url.hostname==='tile.openstreetmap.org')return route.fulfill({status:200,contentType:'image/png',body:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=','base64')});
   return route.fulfill({contentType:'text/html',body:`<style>body{margin:12px;font:15px Arial;background:#eff4f6;--primary-text-color:#183340;--secondary-text-color:#526b78;--card-background-color:white;--secondary-background-color:#eff4f6}ha-card{display:block;background:white;border-radius:14px}</style><gwm-jolion-trips-card></gwm-jolion-trips-card><script src="/gwm-jolion/gwm-jolion-trips-card.js"></script><script src="/gwm-jolion/gwm-jolion-locator-card.js"></script>`});
  });
  await page.goto('https://locator.test');
  await page.waitForFunction(()=>customElements.get('gwm-jolion-locator-card'));
  await page.evaluate(()=>{
   window.card=document.querySelector('gwm-jolion-trips-card');window.calls=[];
   const now=Date.now();window.points=Array.from({length:20},(_,i)=>({timestamp_ms:now-20000+i*1000,latitude:55.75+i*.0001,longitude:37.62+i*.0001,source:'app',accuracy_m:5,speed_accuracy_kmh:1.8,speed_kmh:40+i,speed_estimated:false}));
   window.hass={config:{time_zone:'Europe/Moscow'},states:{'device_tracker.car':{attributes:{golion_locator_enabled:true,latitude:55.75,longitude:37.62}}},callWS:async msg=>{calls.push(msg);return {samples:20,segments:[points.map(p=>[p.latitude,p.longitude])],segment_speeds_kmh:[points.slice(1).map(p=>p.speed_kmh)],segment_kinds:[points.slice(1).map(()=>'moving')],gaps:[],parking_spots:[],km:1.2,method:'gps',playback:points};}};
   card.setConfig({entity:'device_tracker.car',map_style:'osm'});card.hass=hass;
  });
  await page.waitForFunction(()=>card._map&&card._points?.length===20);
  await page.locator('.timeline').fill('5');assert.match(await page.locator('.selected').textContent(),/45 км\/ч.*GPS приложения/);
  assert.match(await page.locator('.selected').textContent(),/GPS ±5 м.*±1.8 км/);
  const selected=await page.evaluate(()=>card._selectedTime);
  await page.evaluate(async()=>{points.unshift({...points[0],timestamp_ms:points[0].timestamp_ms-1000});await card._load();});
  assert.equal(await page.evaluate(()=>card._selectedTime),selected);
  assert.equal(await page.locator('.timeline').inputValue(),'6');
  await page.getByRole('button',{name:'Трек: очищенный',exact:true}).click();
  await page.waitForFunction(()=>calls.at(-1).raw===true);
  assert.equal(await page.evaluate(()=>card._selectedTime),selected);
  await page.getByRole('button',{name:'Трек: исходный',exact:true}).click();
  await page.waitForFunction(()=>!calls.at(-1).raw);
  await page.evaluate(()=>{points.shift();});
  assert.equal(await page.getByRole('button',{name:'Подключить приложение'}).count(),0);
  assert.equal(await page.locator('.stops').count(),0);
  const height=await page.locator('ha-card').evaluate(e=>e.getBoundingClientRect().height);
  await page.evaluate(()=>{window.originalCall=hass.callWS;hass.callWS=msg=>new Promise(resolve=>{window.releaseHistory=()=>resolve(originalCall(msg));});});
  await page.getByRole('button',{name:'Неделя',exact:true}).click();
  assert.equal(await page.evaluate(()=>card._points.length),0,'Previous period must not remain selectable while loading');
  assert(await page.locator('.playback').isHidden());
  await page.evaluate(()=>{hass.callWS=originalCall;releaseHistory();});
  await page.waitForFunction(()=>card._points.length===20);
  await page.waitForFunction(()=>calls.at(-1).start!==calls.at(-1).end);
  await page.getByRole('button',{name:'Выбрать период',exact:true}).click();
  await page.locator('#start').fill('2026-09-20');await page.locator('#end').fill('2026-09-22');await page.locator('#show').click();
  await page.waitForFunction(()=>calls.at(-1).start==='2026-09-20'&&calls.at(-1).end==='2026-09-22');
  await page.evaluate(async()=>{hass.states['device_tracker.car'].attributes.golion_locator_enabled=false;points=points.map(p=>({...p,source:'cloud',speed_estimated:true,accuracy_m:null,speed_accuracy_kmh:null}));card.hass={...hass};await card._load();});
  await page.locator('.timeline').fill('6');assert.match(await page.locator('.selected').textContent(),/≈ 46 км\/ч.*облако/);
  assert(await page.locator('ha-card').evaluate(e=>e.getBoundingClientRect().height)<=height);
  fs.mkdirSync('dist',{recursive:true});await page.screenshot({path:'dist/unified-trips-mobile.png'});
  await page.evaluate(()=>{window.alias=document.createElement('gwm-jolion-locator-card');document.body.append(alias);alias.setConfig({entity:'device_tracker.car',map_style:'osm'});alias.hass=hass;});
  await page.waitForFunction(()=>alias._map&&alias._points?.length===20);
  assert(await page.evaluate(()=>alias instanceof customElements.get('gwm-jolion-trips-card')));
  assert.deepStrictEqual(errors,[]);
  console.log('Unified cloud/app UI, measured/estimated speed, second playback, periods, old card alias and compact layout: PASS');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
