// The locator card is the trips card under its old name: both saved card types
// share one UI. This check runs that UI with the cloud/app source data it gets in
// the field - the map must come up, the route has to be drawn, the always-cleaned
// guarantee has to hold and nothing may sit under the map but the period controls.
const {chromium}=require('playwright');
const fs=require('fs'),path=require('path'),assert=require('assert');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:430,height:850}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/*',route=>{
   const url=new URL(route.request().url());
   if(url.pathname.startsWith('/gwm-jolion/')){const file=path.resolve('custom_components/gwm_jolion/frontend',url.pathname.slice('/gwm-jolion/'.length));if(!fs.existsSync(file))return route.fulfill({status:404,contentType:'text/plain',body:'not found'});return route.fulfill({body:fs.readFileSync(file),contentType:file.endsWith('.css')?'text/css; charset=utf-8':'application/javascript; charset=utf-8'});}
   if(url.hostname==='tiles.openfreemap.org')return route.fulfill({contentType:'application/json',body:JSON.stringify({version:8,sources:{},layers:[{id:'background',type:'background',paint:{'background-color':'#e9ede8'}}]})});
   return route.fulfill({contentType:'text/html',body:`<style>body{margin:12px;font:15px Arial;background:#eff4f6;--primary-text-color:#183340;--secondary-text-color:#526b78;--card-background-color:white;--secondary-background-color:#eff4f6}ha-card{display:block;background:white;border-radius:14px}</style><gwm-jolion-trips-card></gwm-jolion-trips-card><script src="/gwm-jolion/gwm-jolion-trips-card.js"></script><script src="/gwm-jolion/gwm-jolion-locator-card.js"></script>`});
  });
  // Home Assistant registers its own map before any card runs, so the harness does
  // as well: the card then draws on it.
  await page.addInitScript(()=>{customElements.define('ha-map',class extends HTMLElement{
   connectedCallback(){this.style.cssText='display:block;width:100%;height:100%;position:relative';}
   async getMap(){
    if(!this._map){
     const ml=window.GwmTripsMapLibre || window.maplibregl;
     const div=document.createElement('div');div.style.cssText='position:absolute;inset:0;width:100%;height:100%';
     this.append(div);
     this._map=new ml.Map({container:div,attributionControl:false,style:{version:8,sources:{},layers:[{id:'background',type:'background',paint:{'background-color':'#e9ede8'}}]}});
     await new Promise(res=>this._map.once('load',res));
    }
    return this._map;
   }
  });});
  await page.goto('https://locator.test');
  await page.waitForFunction(()=>customElements.get('gwm-jolion-locator-card'));
  await page.evaluate(()=>{
   window.card=document.querySelector('gwm-jolion-trips-card');window.calls=[];
   const now=Date.now();window.points=Array.from({length:20},(_,i)=>({timestamp_ms:now-20000+i*1000,latitude:55.75+i*.0001,longitude:37.62+i*.0001,source:'app',accuracy_m:5,speed_accuracy_kmh:1.8,speed_kmh:40+i,speed_estimated:false}));
   window.hass={config:{time_zone:'Europe/Moscow'},states:{'device_tracker.car':{attributes:{golion_locator_enabled:true,latitude:55.75,longitude:37.62}}},callWS:async msg=>{calls.push(msg);return {samples:20,segments:[points.map(p=>[p.latitude,p.longitude])],segment_speeds_kmh:[points.slice(1).map(p=>p.speed_kmh)],segment_kinds:[points.slice(1).map(()=>'moving')],gaps:[],parking_spots:[],km:1.2,method:'gps',playback:points};}};
   card.setConfig({entity:'device_tracker.car'});card.hass=hass;
  });
  await page.waitForFunction(()=>card._surface&&card._surface.engine==='ha'&&card._surface.hasOverlays());
  // The card is the map and the period: no track strip under the map, no
  // cleaned/raw switch, every request asks for the cleaned track.
  assert.equal(await page.locator('.timeline').count(),0);
  assert.equal(await page.locator('.playback').count(),0);
  assert.equal(await page.getByRole('button',{name:'Трек: очищенный'}).count(),0);
  assert.equal(await page.evaluate(()=>calls.some(msg=>'raw' in msg)),false);
  assert.match(await page.locator('.km').textContent(),/1,2/);
  const height=await page.locator('ha-card').evaluate(e=>e.getBoundingClientRect().height);
  await page.evaluate(()=>{window.originalCall=hass.callWS;hass.callWS=msg=>new Promise(resolve=>{window.releaseHistory=()=>resolve(originalCall(msg));});});
  await page.getByRole('button',{name:'Неделя',exact:true}).click();
  assert.equal(await page.locator('.summary').getAttribute('aria-busy'),'true','пока история грузится, карта помечена занятой');
  await page.evaluate(()=>{hass.callWS=originalCall;releaseHistory();});
  await page.waitForFunction(()=>calls.at(-1).start!==calls.at(-1).end);
  await page.getByRole('button',{name:'Выбрать период',exact:true}).click();
  await page.locator('#start').fill('2026-09-20');await page.locator('#end').fill('2026-09-22');await page.locator('#show').click();
  await page.waitForFunction(()=>calls.at(-1).start==='2026-09-20'&&calls.at(-1).end==='2026-09-22');
  await page.evaluate(async()=>{hass.states['device_tracker.car'].attributes.golion_locator_enabled=false;points=points.map(p=>({...p,source:'cloud',speed_estimated:true,accuracy_m:null,speed_accuracy_kmh:null}));card.hass={...hass};await card._load();});
  assert.match(await page.locator('.km').textContent(),/≈ 1,2/,'облачный режим помечает пробег как оценку');
  assert(await page.locator('ha-card').evaluate(e=>e.getBoundingClientRect().height)<=height);
  fs.mkdirSync('dist',{recursive:true});await page.screenshot({path:'dist/unified-trips-mobile.png'});
  await page.evaluate(()=>{window.alias=document.createElement('gwm-jolion-locator-card');document.body.append(alias);alias.setConfig({entity:'device_tracker.car'});alias.hass=hass;});
  await page.waitForFunction(()=>alias._surface&&alias._surface.hasOverlays());
  assert(await page.evaluate(()=>alias instanceof customElements.get('gwm-jolion-trips-card')));
  assert.deepStrictEqual(errors,[]);
  console.log('Unified cloud/app UI, cleaned track, own-map and HA-map drawing, periods, old card alias and compact layout: PASS');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});