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
   window.hass={config:{time_zone:'Europe/Moscow'},states:{'device_tracker.test':{state:'not_home',attributes:{latitude:55.76,longitude:37.65}}},callWS:async msg=>{calls.push(msg);return structuredClone(sample);}};
   card.setConfig({entity:'device_tracker.test',title:'Поездки · Jolion'});card.hass=hass;
  });
  await page.waitForFunction(()=>card._map && card._layer.getLayers().length===2);
  assert.equal(await page.locator('.map-actions button').count(),2);
  await page.locator('#centerBtn').click();
  await page.waitForFunction(()=>Math.abs(card._map.getCenter().lat-55.76)<0.000001&&Math.abs(card._map.getCenter().lng-37.65)<0.000001);
  assert.equal(await page.evaluate(()=>card._map.getZoom()),16);
  assert.deepEqual(await page.evaluate(()=>({scrollWheelZoom:card._map.options.scrollWheelZoom,dragging:card._map.options.dragging,touchZoom:card._map.options.touchZoom,tap:card._map.options.tap})),{scrollWheelZoom:true,dragging:true,touchZoom:true,tap:true});
  await page.locator('.map').hover();await page.mouse.wheel(0,-400);
  await page.waitForFunction(()=>card._map.getZoom()>16);
  assert.equal(await page.evaluate(()=>card._map.dragging.enabled()),true);
  await page.evaluate(()=>{card._mapCard.requestFullscreen=undefined;});
  await page.locator('#fullscreenBtn').click();
  assert.equal(await page.evaluate(()=>card.classList.contains('fallback-fullscreen')),true);
  assert.equal(await page.locator('#fullscreenBtn').getAttribute('aria-pressed'),'true');
  assert.equal(await page.locator('#fullscreenBtn ha-icon').getAttribute('icon'),'mdi:fullscreen-exit');
  await page.locator('#fullscreenBtn').click();
  assert.equal(await page.evaluate(()=>card.classList.contains('fallback-fullscreen')),false);
  assert.equal(await page.locator('#fullscreenBtn').getAttribute('aria-pressed'),'false');
  await page.waitForFunction(()=>card._base.getMaplibreMap?.().isStyleLoaded());
  assert.equal(await page.evaluate(()=>card._baseStyle),'positron');
  for(const style of ['dark','liberty','osm','positron']){
   await page.evaluate(style=>card.setConfig({...card._config,map_style:style}),style);
   await page.waitForFunction(style=>card._baseStyle===style && card._layer.getLayers().length===2,style);
  }
  await page.evaluate(()=>{
   window.originalMap=GwmTripsMapLibre.Map;
   GwmTripsMapLibre.Map=class {constructor(){throw Error('WebGL unavailable');}};
   card.setConfig({...card._config,map_style:'dark'});
  });
  await page.waitForFunction(()=>card.shadowRoot.querySelector('.map-status').textContent.includes('Показана OpenStreetMap'));
  assert.equal(await page.evaluate(()=>card._layer.getLayers().length),2);
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
  assert.equal(await page.evaluate(()=>card._layer.getLayers().length),3);
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
  await page.evaluate(async()=>{
   sample={...sample,km:12.3,method:'gps',moving_seconds:300,segments:[[[55.75,37.60],[55.751,37.601],[55.752,37.602],[55.753,37.603],[55.754,37.604],[55.755,37.605],[55.755,37.605]]],gaps:[],segment_speeds_kmh:[[79.9,80,95,109.9,110,0]],segment_kinds:[['moving','moving','moving','moving','moving','stationary']],parking_spots:[{latitude:55.74,longitude:37.59,start:1789495200,end:1789498800,duration:3600},{latitude:55.7525,longitude:37.6015,start:1789579200,end:1789586400,duration:7200},{latitude:55.754,longitude:37.603,start:1789586400,end:null,duration:600}]};
   await card._load();
  });
  await page.waitForFunction(()=>card._layer.getLayers().filter(layer=>['#2e7d32','#f9a825','#c62828'].includes(layer.options?.color)).length===5);
  assert.deepEqual(await page.evaluate(()=>card._layer.getLayers().map(layer=>layer.options?.color).filter(color=>['#2e7d32','#f9a825','#c62828'].includes(color))),['#2e7d32','#f9a825','#f9a825','#f9a825','#c62828']);
  assert.equal(await page.locator('.speed-legend').isVisible(),true);
  assert.equal(await page.locator('.speed-legend span').count(),4);
  const parkingMarkers=await page.evaluate(()=>card._layer.getLayers().filter(layer=>layer.options?.icon?.options?.html).map(layer=>layer.options.icon.options.html.textContent));
  assert.deepEqual(parkingMarkers,['A','B','C']);
  const parkingTooltips=await page.evaluate(()=>card._layer.getLayers().filter(layer=>layer.options?.icon?.options?.html).map(layer=>layer.getTooltip().getContent().textContent));
  assert.match(parkingTooltips[0],/Стоянка A.*Начало: \d{2}\.\d{2}\.\d{4}.*Конец:/s);
  assert.match(parkingTooltips[1],/Стоянка B.*Начало: \d{2}\.\d{2}\.\d{4}.*Конец:/s);
  assert.match(parkingTooltips[2],/Стоянка C.*Начало: \d{2}\.\d{2}\.\d{4}/s);
  assert.doesNotMatch(parkingTooltips[2],/Конец:/);
  assert.equal(await page.evaluate(()=>card._layer.getLayers().some(layer=>layer.getTooltip?.()&&/Начало записанного маршрута|Последняя точка/.test(layer.getTooltip().getContent().textContent))),false);
  await page.evaluate(async()=>{card._mode='custom';card._range=['2026-09-16','2026-09-16'];await card._load();});
  await page.waitForFunction(()=>card._layer.getLayers().filter(layer=>layer.options?.icon?.options?.html).length===2);
  const singleDayTooltips=await page.evaluate(()=>card._layer.getLayers().filter(layer=>layer.options?.icon?.options?.html).map(layer=>layer.getTooltip().getContent().textContent));
  assert.match(singleDayTooltips[0],/Стоянка A\nНачало: \d{2}:\d{2}\nКонец: \d{2}:\d{2}/);
  assert.doesNotMatch(singleDayTooltips.join('\n'),/\d{2}\.\d{2}\.\d{4}/);
  await page.evaluate(async()=>{
   const overnightStart=1790173920,overnightEnd=1790225100,firstStart=overnightStart-10800;
   sample={...sample,parking_spots:[
    {latitude:55.70,longitude:37.58,start:firstStart,end:firstStart+1800,duration:1800},
    {latitude:55.71,longitude:37.59,start:firstStart+2400,end:firstStart+4200,duration:1800},
    {latitude:55.72,longitude:37.60,start:firstStart+4800,end:firstStart+6600,duration:1800},
    {latitude:55.73,longitude:37.61,start:overnightStart,end:overnightEnd,duration:14400}
   ]};
   card._mode='custom';card._range=['2026-09-23','2026-09-24'];await card._load();
  });
  await page.waitForFunction(()=>card._layer.getLayers().filter(layer=>layer.options?.icon?.options?.html).length===5);
  const midnightLabels=await page.evaluate(()=>card._layer.getLayers().filter(layer=>layer.options?.icon?.options?.html).map(layer=>layer.options.icon.options.html.textContent));
  assert.deepEqual(midnightLabels,['A','B','C','D','E']);
  assert.equal(await page.evaluate(()=>card._layer.getLayers().filter(layer=>layer.options?.icon?.options?.html).at(-1).options.icon.options.html.style.transform),'translateX(20px)');
  const midnightTooltips=await page.evaluate(()=>card._layer.getLayers().filter(layer=>layer.options?.icon?.options?.html).map(layer=>layer.getTooltip().getContent().textContent));
  assert.doesNotMatch(midnightTooltips[3],/Конец:/);
  assert.match(midnightTooltips[4],/23\.09\.2026.*24\.09\.2026/s);
  await page.evaluate(()=>card.setConfig({...card._config,speed_green_max:85,speed_red_min:100}));
  await page.waitForFunction(()=>card._layer.getLayers().filter(layer=>['#2e7d32','#f9a825','#c62828'].includes(layer.options?.color)).length===5);
  assert.deepEqual(await page.evaluate(()=>card._layer.getLayers().map(layer=>layer.options?.color).filter(color=>['#2e7d32','#f9a825','#c62828'].includes(color))),['#2e7d32','#2e7d32','#f9a825','#c62828','#c62828']);
  assert.equal(await page.locator('.low-range').textContent(),'до 85 км/ч');
  assert.equal(await page.locator('.medium-range').textContent(),'85–100 км/ч');
  assert.equal(await page.locator('.high-range').textContent(),'100+ км/ч');
  await page.evaluate(()=>{window.editor=document.createElement('gwm-jolion-trips-card-editor');document.body.append(editor);window.changedConfig=null;editor.addEventListener('config-changed',event=>changedConfig=event.detail.config);editor.setConfig({entity:'device_tracker.test',map_style:'positron'});editor.hass=hass;});
  await page.waitForFunction(()=>editor._fields?.speed_green_max&&editor._fields?.speed_red_min);
  assert.equal(await page.locator('gwm-jolion-trips-card-editor ha-selector').count(),5);
  assert.deepEqual(await page.evaluate(()=>[editor._fields.speed_green_max.value,editor._fields.speed_red_min.value]),[80,110]);
  await page.evaluate(()=>editor._fields.speed_green_max.dispatchEvent(new CustomEvent('value-changed',{detail:{value:120}})));
  assert.deepEqual(await page.evaluate(()=>changedConfig),{entity:'device_tracker.test',map_style:'positron',speed_green_max:120,speed_red_min:121});
  await page.evaluate(async()=>{
   sample.parking_spots=[{latitude:55.75,longitude:37.60,start:Date.parse('2026-09-16T12:00:00Z')/1000,end:null,observed_until:Date.parse('2026-09-16T12:10:00Z')/1000,duration:600}];
   card._range=['2026-09-16','2026-09-20'];await card._load();
  });
  assert.deepEqual(await page.evaluate(()=>card._layer.getLayers().filter(layer=>layer.options?.icon?.options?.html).map(layer=>layer.options.icon.options.html.textContent)),['A']);
  await page.evaluate(async()=>{card._range=['2026-09-17','2026-09-20'];await card._load();});
  assert.equal(await page.evaluate(()=>card._layer.getLayers().filter(layer=>layer.options?.icon?.options?.html).length),0);
  await page.screenshot({path:path.join(process.env.TEMP,'gwm-trips-card.png'),fullPage:true});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  await page.evaluate(()=>{sample={...sample,samples:0,days:[],segments:[],segment_speeds_kmh:[],segment_kinds:[],parking_spots:[],gaps:[],last:null};card._load();});
  await page.waitForFunction(()=>card.shadowRoot.querySelector('.error').textContent.includes('нет записей'));
  assert.equal(await page.evaluate(()=>card._layer.getLayers().length),0);
  await page.evaluate(()=>{hass.callWS=async()=>{throw Error('Нет доступа');};card._load();});
  await page.waitForFunction(()=>card.shadowRoot.querySelector('.error').textContent==='Нет доступа');
  await page.evaluate(()=>{window.saved=card;card.remove();});
  assert.equal(await page.evaluate(()=>saved._map),null);
  assert.deepEqual(errors,[]);
  console.log('Trips card: route, A/B/C parking points, period-wide labels, date-aware tooltips, configurable speed ranges, centering, map interactions, fullscreen, calendar, visual editor, mobile layout, empty history and errors passed');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
