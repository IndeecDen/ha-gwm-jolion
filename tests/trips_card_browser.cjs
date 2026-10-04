// Browser coverage for the Leaflet trips card currently shipped by the integration.
const {chromium}=require('playwright');
const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');

const root=path.resolve('custom_components/gwm_jolion/frontend');
const html=`<style>body{margin:0;background:#eef2f3;color:#183340;font:15px Arial;--primary-color:#039ecc;--primary-text-color:#183340;--secondary-text-color:#526b78;--secondary-background-color:#eff4f6;--card-background-color:white}ha-card{display:block;background:white}</style><gwm-jolion-trips-card></gwm-jolion-trips-card>`;

(async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
  const page=await browser.newPage({viewport:{width:430,height:1000}}),errors=[];
  page.on('pageerror',error=>errors.push(error.stack||error.message));
  await page.route('**/*',async route=>{
   const url=new URL(route.request().url());
   if(url.pathname.startsWith('/gwm-jolion/')){
    const file=path.resolve(root,url.pathname.slice('/gwm-jolion/'.length));
    if(!fs.existsSync(file))return route.fulfill({status:404,body:'not found'});
    return route.fulfill({body:fs.readFileSync(file),contentType:file.endsWith('.css')?'text/css':'application/javascript'});
   }
   if(url.hostname==='tiles.openfreemap.org')return route.fulfill({contentType:'application/json',body:JSON.stringify({version:8,sources:{},layers:[{id:'background',type:'background',paint:{'background-color':'#e9ede8'}}]})});
   if(url.hostname==='tile.openstreetmap.org')return route.abort();
   return route.fulfill({body:html,contentType:'text/html'});
  });
  await page.goto('http://gwm.test');
  await page.addScriptTag({path:path.join(root,'gwm-jolion-trips-card.js')});
  await page.evaluate(()=>customElements.define('ha-icon',class extends HTMLElement{}));
  await page.evaluate(()=>{
   window.calls=[];window.card=document.querySelector('gwm-jolion-trips-card');
   window.sample={km:5.2,method:'mixed',samples:4,segments:[[[55,37],[55.001,37.001],[55.002,37.002]]],segment_timestamps:[[1791046800,1791046860,1791046920]],segment_speeds_kmh:[[60,65]],segment_kinds:[['moving','moving']],gaps:[],parking_spots:[],source_counts:{app:2,cloud:2},retention_days:90,diagnostics:{locator_enabled:true,recorder_available:true,source_counts:{app:2,cloud:2},retention_days:90}};
   window.hass={config:{time_zone:'Europe/Moscow'},states:{'device_tracker.test':{attributes:{latitude:55,longitude:37}}},callWS:async msg=>{calls.push(msg);return structuredClone(sample);}};
   card.setConfig({entity:'device_tracker.test',map_style:'osm'});card._mode='custom';card._range=['2026-10-03','2026-10-03'];card.hass=hass;
  });
  await page.waitForFunction(()=>card._map&&card._layer&&card._layer.getLayers().length>0);
  assert.equal(await page.locator('.speed-legend').count(),1);
  assert.equal(await page.locator('.speed-legend').textContent().then(text=>text.includes('A, B, C')),false,'бесполезная легенда меток удалена');
  assert.doesNotMatch(await page.locator('.diagnostics').textContent(),/Источники маршрута|Jolion Locator —|GWM —/,'счётчики источников не загромождают карточку');
  assert.equal(await page.evaluate(()=>calls[0].type),'gwm_jolion/trips');
  assert.equal(await page.evaluate(()=>card._layer.getLayers().some(layer=>layer.getLatLng?.().lat===55)),true,'первая точка показана меткой A');

  await page.evaluate(()=>{
   window.editor=document.createElement('gwm-jolion-trips-card-editor');document.body.append(editor);
   editor.setConfig({entity:'device_tracker.test',speed_green_max:80,speed_red_min:110});editor.hass=hass;
  });
  await page.waitForFunction(()=>editor._fields?.speed_green_max&&editor._fields?.speed_red_min);
  await page.evaluate(()=>{
   const field=editor._fields.speed_green_max;field.dispatchEvent(new FocusEvent('focusin',{bubbles:true}));
   field.value='1';field.dispatchEvent(new CustomEvent('value-changed',{detail:{value:'1'}}));
   editor.setConfig({...editor._config,speed_green_max:'1'});
  });
  assert.equal(await page.evaluate(()=>String(editor._fields.speed_green_max.value)),'1','external editor update must not replace an in-progress number');
  await page.evaluate(()=>editor._fields.speed_red_min.dispatchEvent(new CustomEvent('value-changed',{detail:{value:'2'}})));
  assert.equal(await page.evaluate(()=>String(editor._fields.speed_red_min.value)),'110','editing green must not force red threshold to a boundary');

  const parallel=await page.evaluate(async()=>{
   let finish;window.hass.callWS=()=>new Promise(resolve=>{finish=()=>resolve(structuredClone(sample));});
   const before=performance.now();const loading=card._load();
   await new Promise(resolve=>setTimeout(resolve,150));
   const mapWasReady=!!card._map&&!!card._base;
   finish();await loading;
   return {mapWasReady,measures:performance.getEntriesByType('measure').map(entry=>entry.name)};
  });
  assert.equal(parallel.mapWasReady,true,'карта и подложка готовы, пока WebSocket истории ещё ожидается');
  assert(parallel.measures.includes('gwm-trips:history-request'));
  assert(parallel.measures.includes('gwm-trips:map-startup'));
  assert(parallel.measures.includes('gwm-trips:render'));
  await page.evaluate(()=>{hass.callWS=async()=>structuredClone(sample);});

  const cases=[
   [{samples:0,segments:[],gaps:[],source_counts:{app:0,cloud:0},diagnostics:{locator_enabled:false,recorder_available:false,retention_days:90}},/Recorder недоступен.*сбор Jolion Locator выключен.*Нет GPS-координат/i],
   [{samples:0,segments:[],gaps:[],source_counts:{app:0,cloud:0},diagnostics:{locator_enabled:true,recorder_available:true,retention_days:90}},/нет точек от Jolion Locator.*Нет GPS-координат/i],
   [{samples:2,segments:[],gaps:[],source_counts:{app:0,cloud:0},diagnostics:{locator_enabled:true,recorder_available:false,retention_days:90}},/Recorder недоступен.*нет точек от Jolion Locator.*Нет GPS-координат/i],
   [{samples:2,segments:[[[55,37],[55.1,37.1]]],gaps:[[[55,37],[55.1,37.1]]],source_counts:{app:1,cloud:1},diagnostics:{locator_enabled:true,recorder_error:true,source_counts:{app:1,cloud:1},retention_days:90}},/Recorder сейчас недоступен.*Маршрут неполный/i]
  ];
  for(const [data,expected] of cases){
   await page.evaluate(async data=>{sample={...sample,...data};await card._load();},data);
   await page.waitForFunction(expected=>card.shadowRoot.querySelector('.diagnostics').textContent.length>0,expected);
   assert.match(await page.locator('.diagnostics').textContent(),expected);
  }
  await page.evaluate(async()=>{card._range=['2026-01-01','2026-01-01'];sample={...sample,samples:0,segments:[],gaps:[],diagnostics:{locator_enabled:true,recorder_available:true,retention_days:90}};await card._load();});
  assert.match(await page.locator('.diagnostics').textContent(),/история за этот период уже удалена/i);
  assert.deepEqual(errors,[],'карточка не должна генерировать browser errors');
  await page.close();
  console.log('Trips card current Leaflet UI, mixed Locator/GWM sources, missing-data diagnostics, expired retention and removed ABC reminder: PASS');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exit(1);});
