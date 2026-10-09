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
  assert.equal(await page.evaluate(()=>calls[0].skip_recorder),undefined,'first render requests merged history, including parking boundaries');
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

  assert.equal(await page.locator('.download-gpx').isVisible(),false,'GPX export is hidden by default');
  assert.equal(await page.evaluate(()=>editor._fields.show_download_gpx.value),false);
  await page.evaluate(async()=>{
   window.originalSample=structuredClone(sample);
   editor.addEventListener('config-changed',event=>{window.gpxConfig=event.detail.config;});
   editor._fields.show_download_gpx.dispatchEvent(new CustomEvent('value-changed',{detail:{value:true}}));
   card.setConfig({...card._config,show_download_gpx:gpxConfig.show_download_gpx});
   sample={...sample,segments:[[[55,37],[55.001,37.001]],[[56,38],[56.001,38.001]]],segment_timestamps:[[1791046800,1791046860],[null,1791046980]],gaps:[{from:[55.001,37.001],to:[56,38]}]};
   await card._load();card._selectTrip(card._trips[0].key);
  });
  assert.equal(await page.locator('.download-gpx').isVisible(),true);
  const downloading=page.waitForEvent('download');
  await page.locator('.download-gpx').click();
  const gpxDownload=await downloading;
  assert.equal(gpxDownload.suggestedFilename(),'jolion-track-2026-10-03-2026-10-03.gpx');
  const xml=fs.readFileSync(await gpxDownload.path(),'utf8');
  const parsed=await page.evaluate(xml=>{
   const doc=new DOMParser().parseFromString(xml,'application/xml');
   return {error:!!doc.querySelector('parsererror'),version:doc.documentElement.getAttribute('version'),namespace:doc.documentElement.namespaceURI,
    segments:[...doc.querySelectorAll('trkseg')].map(segment=>[...segment.querySelectorAll('trkpt')].map(point=>[point.getAttribute('lat'),point.getAttribute('lon'),point.querySelector('time')?.textContent||null]))};
  },xml);
  assert.equal(parsed.error,false);assert.equal(parsed.version,'1.1');assert.equal(parsed.namespace,'http://www.topografix.com/GPX/1/1');
  assert.deepEqual(parsed.segments,[[['55','37',new Date(1791046800000).toISOString()],['55.001','37.001',new Date(1791046860000).toISOString()]],[['56','38',null],['56.001','38.001',new Date(1791046980000).toISOString()]]],'whole period exported even when a trip is focused, with separate GPS segments and no invented timestamps');
  await page.evaluate(async()=>{
   window.finishGpxHistory=null;hass.callWS=()=>new Promise(resolve=>{finishGpxHistory=resolve;});
   card._range=['2026-10-01','2026-10-02'];window.gpxLoading=card._load();
  });
  assert.equal(await page.locator('.download-gpx').isDisabled(),true,'cannot export previous period while new dates load');
  await page.evaluate(async()=>{finishGpxHistory({...sample,segments:[],samples:0});await gpxLoading;});
  assert.equal(await page.locator('.download-gpx').isDisabled(),true,'no empty GPX download for a period without coordinates');
  await page.evaluate(async()=>{
   sample=originalSample;hass.callWS=async()=>structuredClone(sample);card._range=['2026-10-03','2026-10-03'];
   editor._fields.show_download_gpx.dispatchEvent(new CustomEvent('value-changed',{detail:{value:false}}));
   editor.setConfig(gpxConfig);card.setConfig({...card._config,show_download_gpx:gpxConfig.show_download_gpx});await card._load();
  });
  assert.equal(await page.locator('.download-gpx').isVisible(),false,'editor can hide the GPX button again');
  assert.equal(await page.evaluate(()=>editor._fields.show_download_gpx.value),false);

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
  const overview=await page.evaluate(async()=>{
   sample={...sample,segments:[[[55,37],[55.001,37.001],[55.002,37.002],[55.003,37.003],[55.004,37.004]]],segment_timestamps:[[100,110,120,130,140]],segment_speeds_kmh:[[30,90,120,null]],segment_kinds:[['moving','moving','moving','unknown']],parking_spots:[{start:115,end:120,latitude:55.002,longitude:37.002}]};
   await card._load();
   const colors=card._routeLayer.getLayers().filter(l=>l.options.weight===6).map(l=>l.options.color);
   window.overviewZoom=card._map.getZoom();window.overviewCenter=card._map.getCenter();
   card._routeLayer.getLayers().filter(l=>l.options.className==='route-hit')[1].fire('click');
   return {colors,selected:card._selectedTrip,runs:card._arrowRuns.length,legend:!card.shadowRoot.querySelector('.speed-legend').hidden};
  });
  assert.equal(new Set(overview.colors).size,2,'different parking-to-parking legs have different colors');
  const refresh=await page.evaluate(async()=>{
   const before=card._routeLayer;
   let finish,requests=0,renders=0;
   const render=card._renderTrips.bind(card);
   card._renderTrips=()=>{renders++;return render();};
   hass.callWS=msg=>{requests++;if(msg.skip_recorder)throw Error('partial route requested');return new Promise(resolve=>{finish=resolve;});};
   const loading=card._load();
   const retained=card._routeLayer===before&&card._layer.hasLayer(before);
   finish({...structuredClone(sample),diagnostics:{...sample.diagnostics,recorder_configured:true}});await loading;
   await new Promise(resolve=>setTimeout(resolve,30));
   hass.callWS=async()=>structuredClone(sample);card._renderTrips=render;
   return {retained,requests,renders};
  });
  assert.deepEqual(refresh,{retained:true,requests:1,renders:1},'refresh retains previous route then renders exactly one full snapshot');
  assert.equal(overview.selected,'1');assert.equal(overview.runs,1);assert(overview.legend);
  assert.equal(await page.evaluate(()=>card._routeLayer.getLayers().some(l=>l.options.color==='#c62828')),true);
  await page.evaluate(async()=>{await card._load();});
  assert.equal(await page.evaluate(()=>card._selectedTrip),'1','refresh preserves selection');
  await page.locator('.all-trips').click();
  assert.equal(await page.evaluate(()=>card._selectedTrip),null);
  assert.equal(await page.evaluate(()=>card._map.getZoom()===overviewZoom&&card._map.getCenter().distanceTo(overviewCenter)<1),true,'return restores overview viewport');
  await page.evaluate(()=>card._selectTrip('0'));
  await page.keyboard.press('Escape');
  assert.equal(await page.evaluate(()=>card._selectedTrip),null);
  await page.evaluate(async()=>{card._selectTrip('0');card._range=['2026-10-02','2026-10-03'];await card._load();});
  assert.equal(await page.evaluate(()=>card._selectedTrip),null,'period change resets selection');
  await page.evaluate(async()=>{
   sample={...sample,segments:[[[55,37],[55.001,37.001],[55.002,37.002],[55.003,37.003],[55.004,37.004],[55.005,37.005]]],segment_timestamps:[[100,110,120,130,140,150]],segment_speeds_kmh:[[0,30,90,null,0]],segment_kinds:[['stationary','moving','moving','unknown','stationary']],parking_spots:[{start:90,end:115,latitude:55.0015,longitude:37.0015},{start:135,end:160,latitude:55.0035,longitude:37.0035}]};
   await card._load();card._selectTrip('1');
  });
  const clipped=await page.evaluate(()=>card._trips.find(t=>t.key==='1').runs[0]);
  assert.deepEqual(clipped.points[0],[55.001,37.001],'trip starts with the first fix after the parking interval');
  assert.deepEqual(clipped.points.at(-1),[55.004,37.004],'arrival does not snap to parking marker');
  assert.deepEqual(clipped.speeds,[30,90,null],'parking dwell is excluded while movement speed stays aligned');
  const hover=await page.evaluate(()=>{
   const hit=card._routeLayer.getLayers().find(l=>l.options.className==='route-hit');
   hit.fire('mousemove',{latlng:card._routeContext.L.latLng(55.0025,37.0025)});const known=hit.getTooltip().getContent();
   hit.fire('mousemove',{latlng:card._routeContext.L.latLng(55.00325,37.00325)});return [known,hit.getTooltip().getContent()];
  });
  assert.deepEqual(hover,['Средняя скорость: 90 км/ч','Скорость неизвестна']);
  const retained=await page.evaluate(()=>{
   const segments=[[[55,37],[55.001,37.001],[55.002,37.002]]];
   card._buildTrips({segments,segment_timestamps:[[100,110,120]],parking_spots:[{start:90,end:null,latitude:55,longitude:37}]});
   const openStop=card._trips.flatMap(t=>t.runs).map(r=>r.points);
   card._buildTrips({segments,parking_spots:[{start:90,end:130,latitude:55,longitude:37}]});
   return {openStop,missingTimes:card._trips.flatMap(t=>t.runs).map(r=>r.points)};
  });
  assert.deepEqual(retained.openStop,[],'an open parking interval has no confirmed subsequent trip');
  assert.equal(retained.missingTimes.length,1,'missing timestamps remain visible as an unclassified geometry');
  const conserved=await page.evaluate(()=>{
   const segments=[[[55,37],[55,37.001],[55.001,37.001],[55.001,37.002]],[[55.01,37.01],[55.02,37.02]]];
   const data={segments,segment_timestamps:[[100,200,300,400],[500,600]],parking_spots:[{start:120,end:140,latitude:56,longitude:38},{start:160,end:180,latitude:57,longitude:39},{start:170,end:210,latitude:58,longitude:40}]};
   const edges=runs=>runs.flatMap(points=>points.slice(1).map((p,i)=>JSON.stringify([points[i],p]))).sort();
   const before=JSON.stringify(data);card._buildTrips(data);
   return {expected:edges(segments),actual:edges(card._trips.flatMap(t=>t.runs.map(r=>r.points))),unchanged:JSON.stringify(data)===before};
  });
  assert.deepEqual(conserved.actual,conserved.expected,'every source edge appears exactly once, including overlapping stops and GPS gaps');
  assert(conserved.unchanged,'route grouping leaves source data intact');
  const trafficLight=await page.evaluate(()=>{
   const parking_spots=[{start:50,end:100,latitude:55,longitude:37},{start:500,end:600,latitude:55.004,longitude:37.004}];
   const segments=[[[55,37],[55.001,37.001],[55.001,37.001],[55.002,37.002],[55.004,37.004]]];
   card._buildTrips({segments,segment_timestamps:[[100,150,null,350,500]],parking_spots,segment_speeds_kmh:[[30,0,20,40]]});
   const pause=card._trips.map(t=>({key:t.key,points:t.runs.flatMap(r=>r.points)}));
   card._buildTrips({segments:[segments[0].slice(0,2),segments[0].slice(3)],segment_timestamps:[[100,150],[350,500]],parking_spots});
   return {pause,gap:card._trips.map(t=>({key:t.key,runs:t.runs.length}))};
  });
  assert.equal(trafficLight.pause.length,1,'traffic-light pause stays in the same parking-to-parking trip');
  assert.equal(trafficLight.pause[0].key,'1');
  assert.equal(trafficLight.pause[0].points.length,5,'pause preserves every original point without splitting the run');
  assert.deepEqual(trafficLight.gap,[{key:'1',runs:2}],'real GPS gap remains two geometries but one selectable trip');
  const delayedDeparture=await page.evaluate(async()=>{
   sample={...sample,segments:[[[55,37],[55.001,37],[55.001,37],[55.002,37],[55.003,37]]],segment_timestamps:[[100,150,200,250,300]],segment_speeds_kmh:[[30,0,40,50]],segment_kinds:[['moving','stationary','moving','moving']],parking_spots:[{start:90,end:220,latitude:55,longitude:37},{start:300,end:null,latitude:55.003,longitude:37}]};
   await card._load();
   const hits=card._routeLayer.getLayers().filter(l=>l.options.className==='route-hit');
   hits[0].fire('click');
   return {groups:card._trips.length,hits:hits.length,selected:card._selectedTrip,points:card._arrowRuns[0],speeds:card._trips[0].runs[0].speeds,focusedHits:card._routeLayer.getLayers().filter(l=>l.options.className==='route-hit').length};
  });
  assert.equal(delayedDeparture.groups,1,'parking interval is excluded from selectable trips');
  assert.equal(delayedDeparture.focusedHits,1);
  assert.equal(delayedDeparture.selected,'1');
  assert.equal(delayedDeparture.points.length,3,'selected trip starts after parking and retains its departure');
  assert.deepEqual(delayedDeparture.speeds,[40,50]);
  const stationary=await page.evaluate(async()=>{
   sample={...sample,segments:[[[55,37],[55,37],[55,37]]],segment_timestamps:[[100,110,120]],parking_spots:[]};
   await card._load();return card._routeLayer.getLayers().filter(l=>l.options.className==='route-hit').length;
  });
  assert.equal(stationary,0,'identical parked fixes do not draw stray colored dots');
  const parkedDrift=await page.evaluate(async()=>{
   sample={...sample,segments:[[[55,37],[55.00003,37.00002],[55,37]]],segment_timestamps:[[100,110,120]],segment_kinds:[['stationary','stationary']],segment_speeds_kmh:[[0,0]],parking_spots:[]};
   await card._load();return card._routeLayer.getLayers().filter(l=>l.options.className==='route-hit').length;
  });
  assert.equal(parkedDrift,1,'stationary speed classification must not erase nonzero parking manoeuvres');
  const overviewGaps=await page.evaluate(async()=>{
   sample={...sample,gaps:[[[55,37],[56,38]]],segments:[[[55,37],[55.001,37.001]]],segment_timestamps:[[100,110]],parking_spots:[]};
   await card._load();return card._layer.getLayers().filter(l=>l.options.dashArray==='5 7').length;
  });
  assert.equal(overviewGaps,0,'overview must not draw a false straight connector across a GPS gap');
  const parkingEndpoints=await page.evaluate(async()=>{
   const t=1791176400;
   sample={...sample,segments:[[[55,37],[55.001,37.001]],[[55.002,37.002],[55.003,37.003]]],segment_timestamps:[[t,t+20],[t+40,t+60]],segment_kinds:[['moving'],['moving']],segment_speeds_kmh:[[30],[30]],parking_spots:[{start:t-600,end:t+5,observed_until:t+5,latitude:55.0001,longitude:37},{start:t+60,end:null,observed_until:t+800,latitude:55.0031,longitude:37.003}]};
   card._range=['2026-10-05','2026-10-05'];await card._load();
   const titles=card._overviewLayers.map(l=>l.options.title).filter(Boolean);
   card._selectTrip('1');
   return {titles,tooltips:card._routeLayer.getLayers().map(l=>l.getTooltip?.()?.getContent()).filter(Boolean)};
  });
  assert(!parkingEndpoints.titles.includes('Начало маршрута A'),'initial parking must not have a duplicate route-start marker');
  assert(parkingEndpoints.titles.includes('Стоянка A'));
  assert(parkingEndpoints.tooltips.includes('Начальная стоянка'));
  assert(parkingEndpoints.tooltips.includes('Конечная стоянка'));
  assert(parkingEndpoints.tooltips.includes('Разрыв GPS-записи: точная траектория неизвестна'));
  const downloadPromise=page.waitForEvent('download');
  await page.getByRole('button',{name:'Скачать точки',exact:true}).click();
  const download=await downloadPromise;
  assert.match(download.suggestedFilename(),/^jolion-track-.*\.json$/);
  await page.evaluate(()=>card.setConfig({...card._config,show_download_points:false}));
  assert.equal(await page.getByRole('button',{name:'Скачать точки',exact:true}).count(),0);
  assert.equal(await page.locator('.trip-caption').isVisible(),false);
  await page.setViewportSize({width:390,height:700});
  await page.evaluate(()=>card._setFallbackFullscreen(true));
  await page.getByRole('button',{name:'✕ Закрыть карту',exact:true}).click();
  assert.equal(await page.evaluate(()=>card.classList.contains('fallback-fullscreen')),false);
  await page.locator('#fullscreenBtn').click();
  await page.getByRole('button',{name:'✕ Закрыть карту',exact:true}).click();
  assert.equal(await page.evaluate(()=>card._nativeFullscreen()||card.classList.contains('fallback-fullscreen')),false);

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
