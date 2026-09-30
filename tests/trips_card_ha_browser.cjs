// The trips card can render onto Home Assistant's built-in map (<ha-map>).
//
// The test harness has no <ha-map>, so a stand-in element is registered that hands
// over a real MapLibre map (the same engine HA's map uses). The card then has to
// draw the route as line layers and the parking marker as a MapLibre marker, and
// never fall back to Leaflet.
const {chromium}=require('playwright');
const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome',args:['--enable-unsafe-swiftshader']});
 try{
  const page=await browser.newPage({viewport:{width:430,height:1050}}),errors=[];
  page.on('pageerror',e=>errors.push(e.stack || e.message));
  await page.route('**/*',async route=>{
   const url=new URL(route.request().url());
   if(url.pathname.startsWith('/gwm-jolion/')){
    const file=path.resolve('custom_components/gwm_jolion/frontend',url.pathname.slice('/gwm-jolion/'.length));
    return route.fulfill({body:fs.readFileSync(file),contentType:file.endsWith('.css')?'text/css':'application/javascript'});
   }
   return route.fulfill({body:'<style>body{margin:0;background:#18232a;color:#dde6ed;font-family:Arial;--primary-color:#039ecc;--primary-text-color:#dde6ed;--secondary-text-color:#a4b4c0;--secondary-background-color:#28363d}ha-card{display:block;background:#223039}</style><gwm-jolion-trips-card></gwm-jolion-trips-card>'});
  });
  await page.goto('http://gwm.test');
  await page.addScriptTag({path:path.resolve('custom_components/gwm_jolion/frontend/gwm-jolion-trips-card.js')});
  await page.evaluate(()=>{
   customElements.define('ha-icon',class extends HTMLElement{connectedCallback(){this.textContent=this.getAttribute('icon')==='mdi:counter'?'?':'?';}});
   customElements.define('ha-map',class extends HTMLElement{
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
   });
  });
  await page.evaluate(()=>{
   window.calls=[];window.card=document.querySelector('gwm-jolion-trips-card');
   window.sample={km:1.2,method:'gps',samples:5,segments:[[[55.75,37.60],[55.752,37.61],[55.759,37.62]]],segment_speeds_kmh:[[40,50]],segment_kinds:[['moving','moving']],gaps:[],parking_spots:[{latitude:55.752,longitude:37.61,start:1789560000,end:1789563600,duration:3600}]};
   window.hass={config:{time_zone:'Europe/Moscow'},states:{'device_tracker.test':{state:'not_home',attributes:{latitude:55.76,longitude:37.65}}},callWS:async msg=>{calls.push(msg);return structuredClone(sample);}};
   card.setConfig({entity:'device_tracker.test',title:'Карта',map_engine:'ha'});
   card._mode='custom';card._range=['2026-09-16','2026-09-16'];
   card.hass=hass;
  });
  await page.waitForFunction(()=>window.card._surface && window.card._surface.engine==='ha' && window.card._surface._lines.length>0);
  const state=await page.evaluate(()=>({
   engine:card._surface.engine,
   lines:card._surface._lines.length,
   markers:card._surface._markers.length,
   styleLayers:card._surface.map.getStyle().layers.filter(layer=>layer.type==='line').length,
  }));
  assert.equal(state.engine,'ha');
  assert.ok(state.lines>=1,`ожидался маршрут как line-слой, получено линий ${state.lines}`);
  assert.ok(state.styleLayers>=1,'на карте нет line-слоёв');
  assert.equal(state.markers,1,'стоянка должна быть MapLibre-маркером');
  assert.deepEqual(errors,[]);
  // Switching back to the bundled engine must work without leftovers.
  await page.evaluate(()=>card.setConfig({entity:'device_tracker.test',title:'Карта',map_engine:'leaflet'}));
  await page.waitForFunction(()=>window.card._surface && window.card._surface.engine==='leaflet' && window.card._surface.hasOverlays());
  assert.deepEqual(errors,[]);
  console.log('Trips card on the Home Assistant map: route layers, parking marker, engine switch: PASS');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
