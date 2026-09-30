// The trips card renders onto Home Assistant's own map, <ha-map>, and nowhere else.
//
// The harness has no <ha-map>, so a stand-in is registered that hands over a real
// MapLibre map - the engine Home Assistant's map actually uses. Every line the
// card draws is captured as it is added to the map, so the checks read back exactly
// what the map received rather than what the card believes it drew.
//
// It also checks the two things that were asked for and can silently regress: that
// no second map engine is left in the card (nothing is ever requested from
// /gwm-jolion/leaflet/, there is no map selector in the editor, and no option
// configures a basemap), and that the route is always the cleaned one (there is no
// cleaned/raw button, and the request never carries `raw`).
const {chromium}=require('playwright');
const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');

// A <ha-map> stand-in on top of a real MapLibre map. The map is instrumented so
// every source the card adds is remembered: addSource carries the coordinates,
// and the style carries the colour and dash pattern.
const STUB_MAP=`
 customElements.define('ha-map',class extends HTMLElement{
  connectedCallback(){this.style.cssText='display:block;width:100%;height:100%;position:relative';}
  async getMap(){
   if(!this._map){
    const ml=window.GwmTripsMapLibre || window.maplibregl;
    const div=document.createElement('div');div.style.cssText='position:absolute;inset:0;width:100%;height:100%';
    this.append(div);
    const map=this._map=new ml.Map({container:div,attributionControl:false,style:{version:8,sources:{},layers:[{id:'background',type:'background',paint:{'background-color':'#e9ede8'}}]}});
    window.__draws=new Map();
    const addSource=map.addSource.bind(map),removeSource=map.removeSource.bind(map);
    map.addSource=(id,spec)=>{window.__draws.set(id,spec.data.geometry.coordinates);return addSource(id,spec);};
    map.removeSource=id=>{window.__draws.delete(id);return removeSource(id);};
    await new Promise(res=>map.once('load',res));
   }
   return this._map;
  }
 });
`;
// Read back everything the card put on the map, in draw order. The paint is read
// from the style rather than from getLayer, which hands back MapLibre's live
// internal layer object rather than the spec the card asked for.
//
// A marker's popup only exists once it has been opened, so it is opened, read and
// closed again. That checks the text really reaches the map rather than merely that
// the card built a label somewhere.
const READ_DRAWS=()=>{
 const byId={};
 for(const layer of card._map.getStyle().layers)byId[layer.id]=layer;
 const popupText=marker=>{
  const popup=marker.getPopup();
  if(!popup)return null;
  if(!popup.getElement())marker.togglePopup();
  const text=popup.getElement()?.textContent??null;
  if(popup.isOpen())marker.togglePopup();
  return text;
 };
 return {
  lines:card._surface._lines.map(id=>{const paint=byId[id]?.paint||{};return {coords:(window.__draws.get(id)||[]).map(([lng,lat])=>[lat,lng]),color:paint['line-color'],dash:paint['line-dasharray']||null};}),
  markers:card._surface._markers.map(marker=>({
   text:marker.getElement().textContent,
   offset:marker.getElement().style.marginLeft,
   latlng:[marker.getLngLat().lat,marker.getLngLat().lng],
   popup:popupText(marker)})),
  overlays:card._surface.hasOverlays()};
};

function seed(){
 window.calls=[];window.card=document.querySelector('gwm-jolion-trips-card');
 window.sample={km:14.6,method:'odometer',samples:20,timezone:'Europe/Moscow',retention_days:90,last:1789570800,days:[{date:'2026-09-16',km:14.6,method:'odometer',gaps:1}],segments:[[[55.75,37.60],[55.752,37.61],[55.759,37.62]],[[55.763,37.63],[55.768,37.64]]]};
 window.hass={config:{time_zone:'Europe/Moscow'},states:{'device_tracker.test':{state:'not_home',attributes:{latitude:55.76,longitude:37.65}}},callWS:async msg=>{calls.push(msg);return structuredClone(sample);}};
 card.setConfig({entity:'device_tracker.test',title:'Поездки · Jolion'});
 card._mode='custom';card._range=['2026-09-16','2026-09-16'];
 card.hass=hass;
}

const STUB_LATE=`\n   customElements.define('ha-map',class extends HTMLElement{\n    connectedCallback(){this.style.cssText='display:block;width:100%;height:100%;position:relative';}\n    async getMap(){\n     const ml=window.GwmTripsMapLibre || window.maplibregl;\n     const div=document.createElement('div');div.style.cssText='position:absolute;inset:0;width:100%;height:100%';\n     this.append(div);\n     this.map=new ml.Map({container:div,attributionControl:false,style:{version:8,sources:{},layers:[{id:'background',type:'background',paint:{'background-color':'#e9ede8'}}]}});\n     window.__draws=new Map();\n     await new Promise(res=>this.map.once('load',res));\n     return undefined;\n    }\n   });\n`;
const STUB_SILENT=`\n   customElements.define('ha-map',class extends HTMLElement{\n    connectedCallback(){this.style.cssText='display:block;width:100%;height:100%;position:relative';}\n   });\n`;

async function openCard(browser,stub){
 const page=await browser.newPage({viewport:{width:430,height:1050}}),errors=[],requested=[];
 page.on('pageerror',e=>errors.push(e.stack || e.message));
 // Registered before the first navigation, the way Home Assistant registers its own
 // map, so the card finds <ha-map> on its very first load attempt. After a goto it
 // would only apply to the next navigation, which is never coming.
 if(stub)await page.addInitScript({content:stub});
  await page.route('**/*',async route=>{
  const url=new URL(route.request().url());
  if(url.hostname==='tiles.openfreemap.org')return route.fulfill({contentType:'application/json',body:JSON.stringify({version:8,sources:{},layers:[{id:'background',type:'background',paint:{'background-color':'#e9ede8'}}]})});
  if(url.pathname.startsWith('/gwm-jolion/')){
   requested.push(url.pathname);
   const file=path.resolve('custom_components/gwm_jolion/frontend',url.pathname.slice('/gwm-jolion/'.length));
   // Answer 404 for anything the integration no longer ships, so that a card
   // reaching for a deleted file fails the assertion below rather than crashing
   // the harness on a missing path.
   if(!fs.existsSync(file))return route.fulfill({status:404,contentType:'text/plain',body:'not found'});
   return route.fulfill({body:fs.readFileSync(file),contentType:file.endsWith('.css')?'text/css':'application/javascript'});
  }
  return route.fulfill({body:'<style>body{margin:0;background:#18232a;color:#dde6ed;font-family:Arial;--primary-color:#039ecc;--primary-text-color:#dde6ed;--secondary-text-color:#a4b4c0;--secondary-background-color:#28363d}ha-card{display:block;background:#223039}</style><gwm-jolion-trips-card></gwm-jolion-trips-card>'});
 });
 await page.goto('http://gwm.test');
 await page.addScriptTag({path:path.resolve('custom_components/gwm_jolion/frontend/gwm-jolion-trips-card.js')});
 await page.evaluate(()=>{customElements.define('ha-icon',class extends HTMLElement{connectedCallback(){this.textContent=this.getAttribute('icon')==='mdi:counter'?'◉':'▦';}});});
 await page.evaluate(seed);
 // Count only the speed bands: a stationary run adds its own dashed grey line on
 // top of them, so the total number of lines is not the number of bands.
 await page.evaluate(()=>{window.BANDS=['#2e7d32','#f9a825','#c62828'];window.bandLines=()=>{const byId={};for(const layer of card._map.getStyle().layers)byId[layer.id]=layer;return card._surface._lines.filter(id=>BANDS.includes(byId[id]?.paint?.['line-color']));};});
 return {page,errors,requested};
}

(async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome',args:['--enable-unsafe-swiftshader']});
 try{
  const {page,errors,requested}=await openCard(browser,STUB_MAP);
  // The only vendored thing the card may pull in is MapLibre, and only for the
  // markers it puts on top of Home Assistant's map. Checked before the map itself
  // is awaited, so a card that reached for a second engine is named as such
  // instead of showing up as a map that never opened.
  await page.waitForFunction(()=>card._surface||card.shadowRoot.querySelector('.map-status').textContent.length>0);
  assert.deepEqual([...new Set(requested.filter(url=>url!=='/gwm-jolion/gwm-jolion-trips-card.js'))].sort(),['/gwm-jolion/maplibre/maplibre-gl.css','/gwm-jolion/maplibre/maplibre-gl.js']);
  await page.waitForFunction(()=>card._surface && card._surface.engine==='ha' && card._surface._lines.length===2);
  assert.equal(await page.evaluate(()=>card._surface.engine),'ha');
  assert.equal(await page.locator('.map-actions button').count(),2);
  await page.locator('#centerBtn').click();
  await page.waitForFunction(()=>Math.abs(card._map.getCenter().lat-55.76)<0.000001&&Math.abs(card._map.getZoom()-16)<0.01);
  assert.equal(await page.evaluate(()=>Math.abs(card._map.getCenter().lng-37.65)<0.000001),true);
  // <ha-map> reads its theme off hass, so it has to be handed the current one and
  // not just the one that arrived when the map was created.
  assert.equal(await page.evaluate(()=>{window.hass={...hass,config:{...hass.config}};card.hass=hass;return card._surface._haMap.hass===hass;}),true);
  // The map is pannable and zoomable by hand, like any Home Assistant map.
  assert.deepEqual(await page.evaluate(()=>({scroll:card._map.scrollZoom.isEnabled(),drag:card._map.dragPan.isEnabled(),touch:card._map.touchZoomRotate.isEnabled()})),{scroll:true,drag:true,touch:true});
  await page.locator('.map').hover();await page.mouse.wheel(0,-400);
  await page.waitForFunction(()=>card._map.getZoom()>16);
  await page.evaluate(()=>{card._mapCard.requestFullscreen=undefined;});
  await page.locator('#fullscreenBtn').click();
  assert.equal(await page.evaluate(()=>card.classList.contains('fallback-fullscreen')),true);
  assert.equal(await page.locator('#fullscreenBtn').getAttribute('aria-pressed'),'true');
  assert.equal(await page.locator('#fullscreenBtn ha-icon').getAttribute('icon'),'mdi:fullscreen-exit');
  await page.locator('#fullscreenBtn').click();
  assert.equal(await page.evaluate(()=>card.classList.contains('fallback-fullscreen')),false);
  assert.equal(await page.locator('#fullscreenBtn').getAttribute('aria-pressed'),'false');
  // The basemap is Home Assistant's, not the card's: no option can change it, and
  // the only sources on the map are the route lines the card drew.
  const styleBefore=await page.evaluate(()=>JSON.stringify(card._map.getStyle().layers.filter(layer=>!layer.id.startsWith('gwm-route-'))));
  await page.evaluate(()=>{window.__styleCalls=0;const setStyle=card._map.setStyle.bind(card._map);card._map.setStyle=(...args)=>{window.__styleCalls++;return setStyle(...args);};});
  await page.evaluate(()=>card.setConfig({...card._config,map_style:'dark',map_engine:'leaflet'}));
  await page.waitForFunction(()=>card._surface._lines.length===2);
  assert.equal(await page.evaluate(()=>window.__styleCalls),0);
  assert.equal(await page.evaluate(layers=>JSON.stringify(card._map.getStyle().layers.filter(layer=>!layer.id.startsWith('gwm-route-')))===layers,styleBefore),true);
  assert.equal(await page.evaluate(()=>Object.keys(card._map.getStyle().sources).every(id=>id.startsWith('gwm-route-'))),true);
  // The scale under the map and the cleaned/raw switch are gone.
  assert.equal(await page.locator('.speed-legend').count(),0,'шкала под картой убрана');
  assert.equal(await page.locator('.track-mode').count(),0,'переключатель очищенный/исходный убран');
  await page.waitForFunction(()=>card._surface._lines.length===2);
  assert.equal(await page.evaluate(()=>calls.some(msg=>'raw' in msg)),false,'трек всегда запрашивается очищенным');
  assert.match(await page.locator('.km').textContent(),/14,6/);
  await page.evaluate(async()=>{
   sample.gaps=[[[55.759,37.62],[55.763,37.63]]];
   await card._load();
  });
  let draws=await page.evaluate(READ_DRAWS);
  assert.equal(draws.lines.filter(line=>JSON.stringify(line.dash)==='[5,7]').length,1,'разрыв GPS рисуется пунктиром');
  assert.match(await page.locator('.km').textContent(),/14,6/);
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
  // One line per speed band, not per GPS pair: consecutive pieces of the same
  // colour are gathered so the joins are drawn as one line.
  await page.waitForFunction(()=>window.bandLines().length===3);
  const BANDS=['#2e7d32','#f9a825','#c62828'];
  draws=await page.evaluate(READ_DRAWS);
  assert.deepEqual(draws.lines.map(line=>line.color).filter(color=>BANDS.includes(color)),BANDS);
  // The band is simplified before it reaches the map, so its vertex count is no
  // longer the measured one. What has to hold is that it is still a single line,
  // that it starts and ends on the measured positions, and that it does not leave
  // the measured run by more than the tolerance.
  const amber=draws.lines.filter(line=>line.color==='#f9a825').map(line=>line.coords);
  assert.equal(amber.length,1,'одна линия на диапазон скорости');
  const measured=[[55.75,37.60],[55.751,37.601],[55.752,37.602],[55.753,37.603],[55.754,37.604],[55.755,37.605]];
  // Both ends must be points the phone reported, not something invented.
  const ends=[amber[0][0],amber[0][amber[0].length-1]].map(end=>measured.findIndex(point=>point[0]===end[0]&&point[1]===end[1]));
  for(const [label,index] of [['start',ends[0]],['end',ends[1]]]){
   assert.ok(index>=0,`the band ${label} ${index} is not a measured point`);
  }
  const mPerDegLon=111320*Math.cos(55.754*Math.PI/180);
  const bandOff=point=>{
   const p=[(point[1]-amber[0][0][1])*mPerDegLon,(point[0]-amber[0][0][0])*111320];
   let best=Infinity;
   for(let i=0;i+1<amber[0].length;i++){
    const a=[(amber[0][i][1]-amber[0][0][1])*mPerDegLon,(amber[0][i][0]-amber[0][0][0])*111320];
    const b=[(amber[0][i+1][1]-amber[0][0][1])*mPerDegLon,(amber[0][i+1][0]-amber[0][0][0])*111320];
    const vx=b[0]-a[0],vy=b[1]-a[1],len2=vx*vx+vy*vy;
    let t=len2?((p[0]-a[0])*vx+(p[1]-a[1])*vy)/len2:0;t=t<0?0:(t>1?1:t);
    best=Math.min(best,Math.hypot(p[0]-a[0]-t*vx,p[1]-a[1]-t*vy));
   }
   return best;
  };
  // Only the stretch this band draws is held to the tolerance; the rest of the
  // segment belongs to the other colours and is legitimately far away.
  for(const point of measured.slice(Math.min(...ends),Math.max(...ends)+1)){
   assert.ok(bandOff(point)<=8,`the band strays ${bandOff(point).toFixed(1)} m from the measured run`);
  }
  draws=await page.evaluate(READ_DRAWS);
  assert.deepEqual(draws.markers.map(marker=>marker.text),['A','B','C']);
  assert.match(draws.markers[0].popup,/Стоянка A.*Начало: \d{2}\.\d{2}\.\d{4}.*Конец:/s);
  assert.match(draws.markers[1].popup,/Стоянка B.*Начало: \d{2}\.\d{2}\.\d{4}.*Конец:/s);
  assert.match(draws.markers[2].popup,/Стоянка C.*Начало: \d{2}\.\d{2}\.\d{4}/s);
  assert.doesNotMatch(draws.markers[2].popup,/Конец:/);
  assert.equal(draws.markers.some(marker=>/Начало записанного маршрута|Последняя точка/.test(marker.popup||'')),false);
  // The parking markers live inside the map, below the card's shadow root, so their
  // look has to arrive with the element itself rather than from a stylesheet.
  assert.equal(await page.evaluate(()=>{const el=card._surface._markers[0].getElement();return el.style.borderRadius==='50%'&&el.style.width==='28px'&&el.textContent==='A';}),true,'маркер стилизован сам, а не правилом карточки');
  await page.evaluate(async()=>{
   sample={...sample,parking_spots:[
    {latitude:55.74,longitude:37.59,start:1789495200,end:1789502400,duration:7200},
    {latitude:55.7525,longitude:37.6015,start:1789560000,end:1789590000,duration:30000,inferred:true,inferred_by:'odometer'},
    {latitude:55.7526,longitude:37.6016,start:1789590600,end:1789591200,duration:600,inferred:true,inferred_by:'position'}]};
   await card._load();
  });
  await page.waitForFunction(()=>card._surface._markers.length===3);
  draws=await page.evaluate(READ_DRAWS);
  assert.deepEqual(draws.markers.map(marker=>marker.text),['A','B*','C*']);
  assert.doesNotMatch(draws.markers[0].popup,/выведена/);
  assert.match(draws.markers[1].popup,/Стоянка B\*[\s\S]*Пробег не менялся/);
  assert.match(draws.markers[2].popup,/Стоянка C\*[\s\S]*Пробег рядом недоступен/);
  // With the scale gone from under the map, the popup is the only place left that
  // explains the star, so the explanation has to be there.
  assert.match(draws.markers[1].popup,/выведена по молчанию и пробегу/);
  const plainSpots=[
   {latitude:55.74,longitude:37.59,start:1789495200,end:1789498800,duration:3600},
   {latitude:55.7525,longitude:37.6015,start:1789579200,end:1789586400,duration:7200},
   {latitude:55.754,longitude:37.603,start:1789586400,end:null,duration:600}];
  await page.evaluate(async spots=>{sample={...sample,parking_spots:spots};await card._load();},plainSpots);
  await page.waitForFunction(()=>card._surface._markers.length===3);
  assert.equal((await page.evaluate(READ_DRAWS)).markers.some(marker=>marker.text.includes('*')),false);
  await page.evaluate(async()=>{card._mode='custom';card._range=['2026-09-16','2026-09-16'];await card._load();});
  await page.waitForFunction(()=>card._surface._markers.length===2);
  draws=await page.evaluate(READ_DRAWS);
  assert.match(draws.markers[0].popup,/Стоянка A\nНачало: \d{2}:\d{2}\nКонец: \d{2}:\d{2}/);
  assert.doesNotMatch(draws.markers.map(marker=>marker.popup).join('\n'),/\d{2}\.\d{2}\.\d{4}/);
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
  await page.waitForFunction(()=>card._surface._markers.length===5);
  draws=await page.evaluate(READ_DRAWS);
  // The fourth spot is one parking left across midnight, so it keeps letter D on
  // both nights and the repeat is moved aside. It used to take D and E, which is
  // what made the next stop start at F.
  assert.deepEqual(draws.markers.map(marker=>marker.text),['A','B','C','D','D']);
  assert.equal(draws.markers.at(-1).offset,'20px');
  assert.doesNotMatch(draws.markers[3].popup,/Конец:/);
  assert.match(draws.markers[4].popup,/23\.09\.2026.*24\.09\.2026/s);
  await page.evaluate(async()=>{
   window.savedOvernight=structuredClone(sample.parking_spots);
   sample.parking_spots=[{latitude:55.73,longitude:37.61,start:Date.parse('2026-09-24T17:04:00+03:00')/1000,end:null,observed_until:Date.parse('2026-09-25T00:20:00+03:00')/1000,duration:26040,interruptions:[[Date.parse('2026-09-25T00:03:00+03:00')/1000,Date.parse('2026-09-25T00:05:00+03:00')/1000]]}];
   card._range=['2026-09-25','2026-09-25'];await card._load();
  });
  draws=await page.evaluate(READ_DRAWS);
  assert.match(draws.markers[0].popup,/24\.09\.2026.*17:04/s);
  assert.doesNotMatch(draws.markers[0].popup,/Конец:/);
  assert.match(draws.markers[0].popup,/Нет данных:.*25\.09\.2026.*00:03.*00:05/s);
  assert.equal(draws.markers.length,1);
  await page.evaluate(async()=>{sample.parking_spots=savedOvernight;card._range=['2026-09-23','2026-09-24'];await card._load();});
  await page.evaluate(()=>card.setConfig({...card._config,speed_green_max:85,speed_red_min:100}));
  await page.waitForFunction(()=>window.bandLines().length===3);
  assert.deepEqual((await page.evaluate(READ_DRAWS)).lines.map(line=>line.color).filter(color=>BANDS.includes(color)),BANDS,'диапазоны скорости из настроек по-прежнему применяются');
  await page.evaluate(()=>{window.editor=document.createElement('gwm-jolion-trips-card-editor');document.body.append(editor);window.changedConfig=null;editor.addEventListener('config-changed',event=>changedConfig=event.detail.config);editor.setConfig({entity:'device_tracker.test'});editor.hass=hass;});
  await page.waitForFunction(()=>editor._fields?.speed_green_max&&editor._fields?.speed_red_min);
  // Only the car, the odometer and the two speed limits. No map selector, because
  // there is no map left to choose.
  assert.equal(await page.locator('gwm-jolion-trips-card-editor ha-selector').count(),4);
  assert.equal(await page.evaluate(()=>'map_engine' in editor._fields||'map_style' in editor._fields),false);
  assert.deepEqual(await page.evaluate(()=>[editor._fields.speed_green_max.value,editor._fields.speed_red_min.value]),[80,110]);
  await page.evaluate(()=>editor._fields.speed_green_max.dispatchEvent(new CustomEvent('value-changed',{detail:{value:120}})));
  assert.deepEqual(await page.evaluate(()=>changedConfig),{entity:'device_tracker.test',speed_green_max:120,speed_red_min:121});
  await page.evaluate(async()=>{
   sample.parking_spots=[{latitude:55.75,longitude:37.60,start:Date.parse('2026-09-16T12:00:00Z')/1000,end:null,observed_until:Date.parse('2026-09-16T12:10:00Z')/1000,duration:600}];
   card._range=['2026-09-16','2026-09-20'];await card._load();
  });
  assert.deepEqual((await page.evaluate(READ_DRAWS)).markers.map(marker=>marker.text),['A']);
  await page.evaluate(async()=>{card._range=['2026-09-17','2026-09-20'];await card._load();});
  assert.equal((await page.evaluate(READ_DRAWS)).markers.length,0);
  await page.screenshot({path:path.join(process.env.TEMP,'gwm-trips-card.png'),fullPage:true});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  await page.evaluate(()=>{sample={...sample,samples:0,days:[],segments:[],segment_speeds_kmh:[],segment_kinds:[],parking_spots:[],gaps:[],last:null};card._load();});
  await page.waitForFunction(()=>card.shadowRoot.querySelector('.error').textContent.includes('нет записей'));
  assert.equal(await page.evaluate(()=>card._surface.hasOverlays()),false);
  // Keep recorded traffic-jam edges visible without connecting genuine GPS gaps.
  await page.evaluate(async()=>{
   sample={...sample,samples:8,km:1.2,method:'odometer',parking_spots:[],
    segments:[[[55,37],[55.0001,37],[55.0002,37],[55.0002,37]],[[55.001,37],[55.0011,37]]],
    segment_speeds_kmh:[[4,0,0],[0]],segment_kinds:[['moving','stationary','stationary'],['stationary']],
    gaps:[[[55.0002,37],[55.001,37]]]};
   await card._load();
  });
  draws=await page.evaluate(READ_DRAWS);
  assert.equal(draws.lines.length,4);
  assert.equal(draws.lines.filter(line=>JSON.stringify(line.dash)==='[5,7]').length,1);
  // The wander is simplified like the route, so its vertex count is no longer the
  // measured one. What must hold is that it is still drawn, that both ends stay on
  // the measured positions, and that it never leaves the measured run by more than
  // the tolerance.
  const wander=draws.lines.filter(line=>line.color==='#88949f'&&JSON.stringify(line.dash)==='[2,6]').map(line=>line.coords);
  assert.equal(wander.length,2,'one dashed line per stationary run');
  const wanderMeasured=[[[55.0001,37],[55.0002,37],[55.0002,37]],[[55.001,37],[55.0011,37]]];
  wanderMeasured.forEach((run,index)=>{
   assert.deepEqual(wander[index][0],run[0],`run ${index} must start on the measured point`);
   assert.deepEqual(wander[index][wander[index].length-1],run[run.length-1],`run ${index} must end on the measured point`);
   const mPerDegLon=111320*Math.cos(55.001*Math.PI/180);
   const off=point=>{
    const p=[(point[1]-wander[index][0][1])*mPerDegLon,(point[0]-wander[index][0][0])*111320];
    let best=Infinity;
    for(let i=0;i+1<wander[index].length;i++){
     const a=[(wander[index][i][1]-wander[index][0][1])*mPerDegLon,(wander[index][i][0]-wander[index][0][0])*111320];
     const b=[(wander[index][i+1][1]-wander[index][0][1])*mPerDegLon,(wander[index][i+1][0]-wander[index][0][0])*111320];
     const vx=b[0]-a[0],vy=b[1]-a[1],len2=vx*vx+vy*vy;
     let t=len2?((p[0]-a[0])*vx+(p[1]-a[1])*vy)/len2:0;t=t<0?0:(t>1?1:t);
     best=Math.min(best,Math.hypot(p[0]-a[0]-t*vx,p[1]-a[1]-t*vy));
    }
    return best;
   };
   for(const point of run)assert.ok(off(point)<=8,`run ${index} strays ${off(point).toFixed(1)} m from the measured wander`);
  });
  // A stationary run that sits on a parking marker is the receiver wandering; the
  // marker already says the car stood there, so the wander is not drawn.
  await page.evaluate(async()=>{
   sample={...sample,km:1.2,method:'gps',samples:6,moving_seconds:120,
    segments:[[[55,37],[55.0001,37],[55.0002,37],[55.0003,37]]],
    segment_speeds_kmh:[[0,0,0]],segment_kinds:[['stationary','stationary','stationary']],
    gaps:[],parking_spots:[{latitude:55.0002,longitude:37,start:1789495200,end:1789498800,duration:3600}]};
   await card._load();
  });
  // Still drawn: omitting it tore holes in the route at every stop. Softened, not removed.
  assert.equal((await page.evaluate(READ_DRAWS)).lines.filter(line=>line.color==='#88949f').length,1,'the parked wander must stay on the map');
  assert.match(await page.locator('.km').textContent(),/1,2/);
  await page.evaluate(()=>{sample={...sample,samples:0,segments:[],segment_speeds_kmh:[],segment_kinds:[],gaps:[],parking_spots:[]};});
  // At 00:08 no driving line or ten-minute parking marker is required to show the car.
  await page.clock.install({time:new Date('2026-09-24T21:08:00Z')});
  await page.evaluate(async()=>{card._mode='today';sample.last_position=null;await card._load();});
  assert.equal(await page.evaluate(()=>calls.at(-1).start),'2026-09-25');
  draws=await page.evaluate(READ_DRAWS);
  assert.equal(draws.markers.length,1);
  assert.match(draws.markers[0].popup,/Последнее известное/);
  assert.equal(await page.locator('.km').textContent(),'—');
  await page.evaluate(async()=>{
   hass.states['device_tracker.test']={state:'unavailable',attributes:{latitude:null,longitude:null}};
   sample.last_position={latitude:55,longitude:37,observed_at:Date.parse('2026-09-24T20:55:00Z')/1000};
   await card._load();
  });
  assert.equal((await page.evaluate(READ_DRAWS)).markers[0].latlng[0],55);
  await page.evaluate(async()=>{card._mode='yesterday';await card._load();});
  assert.equal(await page.evaluate(()=>card._surface.hasOverlays()),false);
  await page.evaluate(async()=>{card._mode='today';sample.last_position=null;await card._load();});
  assert.equal(await page.evaluate(()=>card._surface.hasOverlays()),false);
  await page.evaluate(()=>{hass.callWS=async()=>{throw Error('Нет доступа');};card._load();});
  await page.waitForFunction(()=>card.shadowRoot.querySelector('.error').textContent==='Нет доступа');
  // Anything raised while the card was on screen is a real fault and fails here.
  const whileAlive=errors.slice();
  await page.evaluate(()=>{window.saved=card;card.remove();});
  assert.equal(await page.evaluate(()=>saved._map),null);
  // Removing the card tears the map down while MapLibre still has a render queued.
  // It then throws from its own internals about the destroyed map, and with the
  // clock faked above the timing shifts from run to run. That is teardown noise,
  // so it is named and excluded - anything else during removal still fails.
  const teardownNoise=/maplibre-gl\.js|_render|getZoom|projection/;
  const afterRemoval=errors.slice(whileAlive.length).filter(text=>!teardownNoise.test(text));
  assert.deepEqual(whileAlive,[],'the card must not raise errors while it is on screen');
  assert.deepEqual(afterRemoval,[],'removal must raise nothing but the dead render loop');
  await page.close();

// Without <ha-map> there is no Home Assistant map to draw on, and that must
  // not mean the track is lost: the card draws the route on its own map at once.
  const bare=await openCard(browser,null);
  await bare.page.waitForFunction(()=>card._surface&&card._surface.engine==='ha'&&card._surface._lines.length===2);
  assert.equal(await bare.page.locator('.map-status').textContent(),'');
  assert.equal(await bare.page.evaluate(()=>card._surface.hasOverlays()),true,'трек нарисован на собственной карте');
  assert.equal(await bare.page.locator('.km').textContent(),'14,6','пробег остаётся доступен');
  assert.deepEqual(bare.errors,[]);
  await bare.page.close();

  // Home Assistant builds its map in firstUpdated, so getMap() can hand back
  // nothing on the first call. The card then reads the map off the element and
  // draws on it as usual.
  const late=await openCard(browser,STUB_LATE);
  await late.page.waitForFunction(()=>card._surface && card._surface.engine==='ha' && card._surface._lines.length===2);
  assert.equal(await late.page.evaluate(()=>card._surface.hasOverlays()),true,'маршрут лёг на карту, которая не отдала getMap');
  assert.deepEqual(late.errors,[]);
  await late.page.close();

  // A map element that exists but refuses to hand over a usable map: the route
  // still has to be drawn, so the card falls to its own map, silently.
  const silent=await openCard(browser,STUB_SILENT);
  await silent.page.waitForFunction(()=>card._surface&&card._surface._lines.length===2);
  assert.equal(await silent.page.locator('.map-status').textContent(),'');
  assert.equal(await silent.page.evaluate(()=>card._surface.hasOverlays()),true,'трек нарисован, хотя карта HA не отдала карту');
  assert.equal(await silent.page.locator('.km').textContent(),'14,6','пробег остаётся доступен');
  assert.equal(await silent.page.locator('[data-mode="today"]').count(),1,'выбор периода остаётся доступен');
  assert.deepEqual(silent.errors,[]);
  await silent.page.close();

  // The card must open as fast as Home Assistant's own map card: it does not wait
  // for the element to turn up, it draws on its own map straight away.
  const lazy=await openCard(browser,null);
  const t0=await lazy.page.evaluate(()=>performance.now());
  await lazy.page.waitForFunction(()=>card._surface&&card._surface._lines.length===2);
  const elapsed=(await lazy.page.evaluate(()=>performance.now()))-t0;
  assert.ok(elapsed<5000,'карта поднялась за '+elapsed.toFixed(0)+' мс, а не после ожидания Home Assistant');
  assert.equal(await lazy.page.evaluate(()=>card._surface.hasOverlays()),true,'трек на собственной карте');
  assert.equal(await lazy.page.locator('.map-status').textContent(),'');
  assert.deepEqual(lazy.errors,[]);
  await lazy.page.close();

  // A future interface release is free to rename the element. Pinning one tag name
  // would break the card on that day with no explanation; the card looks the known
  // names up in turn instead.
  const renamed=await openCard(browser,`
   customElements.define('ha-map-entity',class extends HTMLElement{
    connectedCallback(){this.style.cssText='display:block;width:100%;height:100%;position:relative';}
    async getMap(){
     const ml=window.GwmTripsMapLibre || window.maplibregl;
     const div=document.createElement('div');div.style.cssText='position:absolute;inset:0;width:100%;height:100%';
     this.append(div);
     this._map=new ml.Map({container:div,attributionControl:false,style:{version:8,sources:{},layers:[{id:'background',type:'background',paint:{'background-color':'#e9ede8'}}]}});
     window.__draws=new Map();
     await new Promise(res=>this._map.once('load',res));
     return this._map;
    }
   });
  `);
  assert.equal(await renamed.page.evaluate(()=>!!customElements.get('ha-map')),false,'старого имени нет');
  await renamed.page.waitForFunction(()=>card._surface&&card._surface.engine==='ha'&&card._surface._lines.length===2,null,{timeout:20000});
  assert.equal(await renamed.page.evaluate(()=>card._surface.hasOverlays()),true,'маршрут лёг на переименованный элемент карты');
  assert.deepEqual(renamed.errors,[]);
  await renamed.page.close();

  console.log('Trips card on the Home Assistant map: route lines, A/B/C parking points, period-wide labels, date-aware popups, configurable speed ranges, centering, map interaction, fullscreen, calendar, no second map engine, always-cleaned track, late, renamed, own-map fallback, fast-open, mobile layout, empty history and errors: PASS');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
