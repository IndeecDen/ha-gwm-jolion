// Cost and cache coverage for the Leaflet trips card: a long route must paint
// without keeping a per-fix copy of the invisible click corridor, hovering a
// focused trip must not re-project the whole run for every mouse event, and a
// periodic refresh that returns the very same payload must not rebuild the map.
const {chromium}=require('playwright');
const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');

const root=path.resolve('custom_components/gwm_jolion/frontend');
const html=`<style>body{margin:0;background:#eef2f3;color:#183340;font:15px Arial;--primary-color:#039ecc;--primary-text-color:#183340;--secondary-text-color:#526b78;--secondary-background-color:#eff4f6;--card-background-color:white}ha-card{display:block;background:white}</style><gwm-jolion-trips-card></gwm-jolion-trips-card>`;
const VERSION='9.9.9';

function payload(){
 const segments=[],timestamps=[],speeds=[],kinds=[];
 let clock=1791046800;
 for(let segment=0;segment<3;segment++){
  const points=[],times=[],segmentSpeeds=[],segmentKinds=[];
  let lat=55+segment*0.02,lon=37+segment*0.02;
  for(let index=0;index<2500;index++){
   lat+=0.00012;lon+=index%400<200?0.00009:-0.00004;
   // Urban GPS noise: a few metres either side of the street.
   const noise=Math.sin(index*1.7)*0.00011;
   points.push([Number((lat+noise).toFixed(6)),Number((lon-noise*0.7).toFixed(6))]);
   clock+=10;times.push(clock);segmentSpeeds.push(20+(index%7)*5);segmentKinds.push('moving');
  }
  segments.push(points);timestamps.push(times);speeds.push(segmentSpeeds);kinds.push(segmentKinds);clock+=600;
 }
 return {km:64.2,method:'mixed',samples:7500,segments,segment_timestamps:timestamps,segment_speeds_kmh:speeds,
  segment_kinds:kinds,gaps:[],parking_spots:[],source_counts:{app:0,cloud:7500},retention_days:90,
  diagnostics:{locator_enabled:true,recorder_available:true,source_counts:{app:0,cloud:7500},retention_days:90}};
}

// Metres from a fix to the nearest drawn segment, mirroring the projection the
// card uses so the tolerance in the test means the same thing on screen.
const DEGREE_M=111320;
function metres(points,index,geometry){
 const lat0=geometry[0][0],mLon=DEGREE_M*Math.cos(lat0*Math.PI/180);
 const px=(points[index][1]-geometry[0][1])*mLon,py=(points[index][0]-geometry[0][0])*DEGREE_M;
 let best=Infinity;
 for(let step=1;step<geometry.length;step++){
  const ax=(geometry[step-1][1]-geometry[0][1])*mLon,ay=(geometry[step-1][0]-geometry[0][0])*DEGREE_M;
  const bx=(geometry[step][1]-geometry[0][1])*mLon,by=(geometry[step][0]-geometry[0][0])*DEGREE_M;
  const dx=bx-ax,dy=by-ay,length=dx*dx+dy*dy;
  const fraction=length?Math.max(0,Math.min(1,((px-ax)*dx+(py-ay)*dy)/length)):0;
  const distance=(px-ax-fraction*dx)**2+(py-ay-fraction*dy)**2;
  if(distance<best)best=distance;
 }
 return Math.sqrt(best);
}

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
   if(url.hostname==='tile.openstreetmap.org')return route.abort();
   return route.fulfill({body:html,contentType:'text/html'});
  });
  await page.goto('http://gwm.test');
  // Lovelace requests the card with the integration version as the cache key.
  await page.addScriptTag({url:`http://gwm.test/gwm-jolion/gwm-jolion-trips-card.js?v=${VERSION}`});
  await page.evaluate(()=>customElements.define('ha-icon',class extends HTMLElement{}));
  await page.evaluate(data=>{
   window.calls=[];window.card=document.querySelector('gwm-jolion-trips-card');window.sample=data;
   window.hass={config:{time_zone:'Europe/Moscow'},states:{'device_tracker.test':{attributes:{latitude:55,longitude:37}}},callWS:async msg=>{calls.push(msg);return structuredClone(sample);}};
   card.setConfig({entity:'device_tracker.test',map_style:'osm'});card._mode='custom';card._range=['2026-10-03','2026-10-03'];card.hass=hass;
  },payload());
  await page.waitForFunction(()=>card._map&&card._routeLayer&&card._routeLayer.getLayers().length>0);

  // 1. The invisible click corridor follows the painted line instead of a copy
  // of every fix, and thinning it must not move the route.
  const geometry=await page.evaluate(()=>{
   const hit=card._routeLayer.getLayers().find(layer=>layer.options.className==='route-hit');
   const painted=card._routeLayer.getLayers().filter(layer=>layer.options.className!=='route-hit');
   return {hit:hit.getLatLngs().map(point=>[point.lat,point.lng]),
    painted:painted.map(layer=>layer.getLatLngs().length),
    raw:card._trips.flatMap(trip=>trip.runs).reduce((total,run)=>total+run.points.length,0),
    first:card._trips[0].runs[0].points};
  });
  assert.equal(geometry.raw,7500,'the fixture stays a week-sized route');
  assert.ok(geometry.hit.length<geometry.first.length*0.5,
   `hit corridor keeps ${geometry.hit.length} of ${geometry.first.length} fixes`);
  assert.equal(geometry.painted.length,6,'a trip run still paints its white casing and its coloured line');
  const sorted=[...geometry.painted].sort((left,right)=>left-right);
  for(let index=0;index<sorted.length;index+=2)
   assert.equal(sorted[index],sorted[index+1],'casing and colour of one run share one geometry');
  assert.equal(sorted[0],geometry.hit.length,'the corridor follows the painted line instead of a second copy');
  let worst=0;
  for(let index=0;index<geometry.first.length;index+=7)worst=Math.max(worst,metres(geometry.first,index,geometry.hit));
  assert.ok(worst<=8.5,`simplification keeps the recorded route within ${worst.toFixed(2)} m`);

  // 2. Hovering reprojects the run once per view, not once per mouse event.
  const hover=await page.evaluate(()=>{
   card._selectTrip('0');
   const hit=card._routeLayer.getLayers().find(layer=>layer.options.className==='route-hit');
   const element=hit.getElement(),original=card._map.latLngToContainerPoint.bind(card._map);
   let counted=0;card._map.latLngToContainerPoint=latlng=>{counted++;return original(latlng);};
   const cursor=original(hit.getLatLngs()[20]);
   // The first event of a new view has to project the run; the rest ride on it.
   element.dispatchEvent(new MouseEvent('mousemove',{clientX:cursor.x,clientY:cursor.y,bubbles:true}));
   counted=0;
   const measured=performance.now();
   for(let index=0;index<6;index++)element.dispatchEvent(new MouseEvent('mousemove',{clientX:cursor.x,clientY:cursor.y,bubbles:true}));
   const warmMs=performance.now()-measured;
   const warm=counted;
   card._map.setZoom(card._map.getZoom()+1,{animate:false});
   counted=0;
   const coldStarted=performance.now();
   element.dispatchEvent(new MouseEvent('mousemove',{clientX:cursor.x,clientY:cursor.y,bubbles:true}));
   const cold=counted,coldMs=performance.now()-coldStarted;
   return {warm,cold,warmMs,coldMs,focused:card._arrowRuns[0].length};
  });
  assert.ok(hover.cold>=hover.focused,'a new view reprojects the focused run');
  // Four projections per mouse event: the hover prefilter narrows to a window
  // before measuring, so the cost does not follow the run length.
  assert.ok(hover.warm<=36,`six mouse events cost ${hover.warm} projections for ${hover.focused} fixes`);
  assert.ok(hover.warmMs<250,`six hover events took ${hover.warmMs.toFixed(1)} ms`);

  // 3. A refresh that returns the same payload keeps the painted map.
  const refresh=await page.evaluate(async()=>{
   card._selectTrip(null);
   const layer=card._routeLayer,before=layer.getLayers().length;
   await card._load();
   const kept=card._routeLayer===layer&&layer.getLayers().length===before;
   sample={...sample,segments:sample.segments.map((segment,index)=>index?segment:[...segment,[56,38]]),
    segment_timestamps:sample.segment_timestamps.map((times,index)=>index?times:[...times,times.at(-1)+10])};
   await card._load();
   return {kept,rebuilt:card._routeLayer!==layer};
  });
  assert.equal(refresh.kept,true,'an unchanged payload must not rebuild thousands of vertices');
  assert.equal(refresh.rebuilt,true,'a changed payload is painted again');

  // 4. Vendored map libraries are requested with the version of the card itself
  // so the browser can keep them for as long as Home Assistant caches them.
  const assets=await page.evaluate(()=>performance.getEntriesByType('resource')
   .map(entry=>entry.name).filter(name=>/\/gwm-jolion\/(leaflet|maplibre)\//.test(name)));
  assert.ok(assets.length>=2,`vendored libraries were requested: ${assets.join(', ')}`);
  for(const name of assets)assert.equal(new URL(name).searchParams.get('v'),VERSION,`${name} carries the card version`);
  const source=fs.readFileSync(path.join(root,'gwm-jolion-trips-card.js'),'utf8');
  const literals=[...source.matchAll(/['"`]\/gwm-jolion\/(?:leaflet|maplibre)\//g)].length;
  const wrapped=[...source.matchAll(/assetUrl\(\s*['"`]\/gwm-jolion\/(?:leaflet|maplibre)\//g)].length;
  assert.ok(literals>0,'the card still loads vendored libraries');
  assert.equal(literals,wrapped,'every library URL goes through the versioning helper');

  const timings=await page.evaluate(()=>{
   let started=performance.now();card._renderTrips();const overview=performance.now()-started;
   started=performance.now();card._selectTrip('0');const focus=performance.now()-started;
   started=performance.now();card._drawChevrons();const chevrons=performance.now()-started;
   return {overview,focus,chevrons};
  });
  assert.ok(timings.focus<2000,`focusing a ${geometry.raw}-fix route took ${timings.focus.toFixed(0)} ms`);
  assert.deepEqual(errors,[]);
  console.log(`Trips perf: ${geometry.raw} fixes, corridor ${geometry.hit.length} fixes, max deviation ${worst.toFixed(2)} m, `+
   `hover ${hover.warm} projections / ${hover.warmMs.toFixed(1)} ms (cold ${hover.cold} / ${hover.coldMs.toFixed(1)} ms), `+
   `render ${timings.overview.toFixed(0)} ms, focus ${timings.focus.toFixed(0)} ms, arrows ${timings.chevrons.toFixed(0)} ms: passed`);
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exit(1);});
