/* GWM Jolion Trips Card v0.2.0-beta.3 */
(() => {
  const SPEED_COLORS = {low:'#2e7d32',medium:'#f9a825',high:'#c62828'};
  const DEFAULT_SPEED_LIMITS = {green:80,red:110};
  function speedLimits(config={}){
    const limit=(value,fallback)=>{const number=Number(value);return value!==null&&value!==undefined&&value!==''&&Number.isFinite(number)?Math.max(1,Math.min(300,Math.round(number))):fallback;};
    let green=limit(config.speed_green_max,DEFAULT_SPEED_LIMITS.green),red=limit(config.speed_red_min,DEFAULT_SPEED_LIMITS.red);
    if(green>=300)green=299;
    if(red<=green)red=Math.min(300,green+1);
    return {green,red};
  }
  let mapLibre;
  function loadScript(src){return new Promise((resolve,reject)=>{
    const script=document.createElement('script');const timer=setTimeout(()=>{script.remove();reject(new Error('Не удалось загрузить карту'));},15000);
    script.src=src;script.onload=()=>{clearTimeout(timer);resolve();};script.onerror=()=>{clearTimeout(timer);script.remove();reject(new Error('Не удалось загрузить карту'));};document.head.append(script);
  });}
  // The route is drawn on Home Assistant's own map, <ha-map>. MapLibre is only
  // needed to build the markers and popups that go on top of it, so the build
  // shipped with the integration is loaded into a private slot: Home Assistant has
  // already set window.maplibregl to its own copy and overwriting it would break
  // the very map being drawn on.
  function loadMapLibre(){return mapLibre ||= (async()=>{
    if(!window.GwmTripsMapLibre){
      const previous=window.maplibregl;
      await loadScript('/gwm-jolion/maplibre/maplibre-gl.js');
      window.GwmTripsMapLibre=window.maplibregl;window.maplibregl=previous;
    }
    return window.GwmTripsMapLibre;
  })().catch(error=>{mapLibre=null;throw error;});}
  function dateInZone(zone) {
    const parts = new Intl.DateTimeFormat('en', {timeZone: zone, year:'numeric', month:'2-digit', day:'2-digit'}).formatToParts(new Date());
    const get = type => parts.find(p => p.type === type).value;
    return `${get('year')}-${get('month')}-${get('day')}`;
  }
  function shift(day, count) {
    const value = new Date(`${day}T12:00:00Z`); value.setUTCDate(value.getUTCDate()+count);
    return value.toISOString().slice(0,10);
  }
  function tripTime(value, zone, withDate=false){const options=withDate?{timeZone:zone,day:'2-digit',month:'2-digit',year:'numeric',hour:'2-digit',minute:'2-digit'}:{timeZone:zone,hour:'2-digit',minute:'2-digit'};return new Intl.DateTimeFormat('ru-RU',options).format(new Date(value*1000));}
  function dayInZone(value, zone){const parts=new Intl.DateTimeFormat('en',{timeZone:zone,year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date(value*1000)),get=type=>parts.find(part=>part.type===type).value;return `${get('year')}-${get('month')}-${get('day')}`;}
  function dateRange(start,end){const dates=[],last=new Date(`${end}T00:00:00Z`);for(let value=new Date(`${start}T00:00:00Z`);value<=last;value.setUTCDate(value.getUTCDate()+1))dates.push(value.toISOString().slice(0,10));return dates;}
  function pointLabel(index){let value=index,label='';do{label=String.fromCharCode(65+value%26)+label;value=Math.floor(value/26)-1;}while(value>=0);return label;}
  function parkingOccurrences(spots,start,end,zone){let sequence=0;const spotLabels={},spotOffsets={};return spots.flatMap(spot=>{const started=Number(spot.start),ended=spot.end===null||spot.end===undefined?NaN:Number(spot.end),startDay=dayInZone(started,zone),endDay=dayInZone(Number.isFinite(ended)?ended:Number(spot.observed_until ?? (started+Number(spot.duration || 0))),zone),spotKey=`${spot.latitude}|${spot.longitude}|${spot.start}|${spot.end}`;return dateRange(start,end).filter(day=>startDay<=day&&(!endDay||day<=endDay)).map(day=>{if(!(spotKey in spotLabels))spotLabels[spotKey]=pointLabel(sequence++);const offset=spotOffsets[spotKey]||0;spotOffsets[spotKey]=offset+1;return {...spot,day,label:spotLabels[spotKey],offset_index:offset,show_end:Number.isFinite(ended)&&day===endDay};});});}
  // Distance between two [lat,lon] points, in metres.
  function metersBetween(a,b){
    const rad=Math.PI/180,lat1=a[0]*rad,lat2=b[0]*rad;
    const h=Math.sin((b[0]-a[0])*rad/2)**2+Math.cos(lat1)*Math.cos(lat2)*Math.sin((b[1]-a[1])*rad/2)**2;
    return 12742*Math.asin(Math.min(1,Math.sqrt(h)));
  }
  // Group the edges a stationary run covers, so the whole run is judged at once.
  function stationaryRuns(segment,kinds){
    const runs=new Map();let current=null;
    for(let i=1;i<segment.length;i++){
      if(kinds[i-1]==='stationary'){
        if(!current){current={points:[segment[i-1]],end:i};runs.set(i,current);}
        current.points.push(segment[i]);current.end=i;
      }else current=null;
    }
    return runs;
  }
  function runCentre(points){
    return [points.reduce((s,p)=>s+p[0],0)/points.length,points.reduce((s,p)=>s+p[1],0)/points.length];
  }
  // A parking marker already says the car stood here, so the receiver's wander
  // underneath it is noise; but the segment must still be drawn, because omitting
  // it leaves a hole in the route.
  const PARKED_NEAR_M=200;
  const EARTH_M=111320;
  // Douglas-Peucker simplification of the drawn route.
  //
  // The route reaches the map decimated to roughly 13 m per point, and the median
  // interior vertex of the real data is a 179 degree reversal: the parked receiver
  // jittering back and forth, not a corner. Rounding that sawtooth either left it
  // alone or cut the route by 100 m. Dropping the points inside a small tolerance
  // removes it without inventing anything - the result is a subset of the measured
  // points, both ends stay exactly where the phone put them, and no measured point
  // ends up further than the tolerance from the line that is drawn.
  //
  // The tolerance has to clear the jitter. The median step is 12.8 m, so the
  // sawtooth swings about 6.4 m and a 4 m tolerance removed nothing at all; 8 m
  // drops 80% of the real route's points and never moves the line further than
  // that, where the reverted rounding reached 100 m.
  //
  // Applied to the speed bands and the plain route. Not to the GPS gap lines: those
  // already mean "no data here", and smoothing them would draw a path nobody drove.
  function simplifyPath(points,tolerance){
    const limit=Number(tolerance)||8;
    if(!Array.isArray(points)||points.length<3)return points;
    const mLon=EARTH_M*Math.cos(points[0][0]*Math.PI/180);
    const xy=points.map(point=>[(point[1]-points[0][1])*mLon,(point[0]-points[0][0])*EARTH_M]);
    const keep=new Uint8Array(points.length);
    keep[0]=1;keep[points.length-1]=1;
    const stack=[[0,points.length-1]];
    while(stack.length){
      const [first,last]=stack.pop();
      if(last<=first+1)continue;
      const a=xy[first],b=xy[last];
      const vx=b[0]-a[0],vy=b[1]-a[1],len2=vx*vx+vy*vy;
      let worst=-1,worstAt=-1;
      for(let i=first+1;i<last;i++){
        const p=xy[i];
        let t=len2?((p[0]-a[0])*vx+(p[1]-a[1])*vy)/len2:0;
        t=t<0?0:(t>1?1:t);
        const d=Math.hypot(p[0]-a[0]-t*vx,p[1]-a[1]-t*vy);
        if(d>worst){worst=d;worstAt=i;}
      }
      if(worst>limit){keep[worstAt]=1;stack.push([first,worstAt],[worstAt,last]);}
    }
    return points.filter((_,index)=>keep[index]);
  }
  // A marker is handed to MapLibre, which appends it into the map - below this
  // card's shadow root - so the card's stylesheet cannot reach it. Its look is
  // therefore set inline.
  //
  // The offset that moves a parking repeated on several days aside goes on the
  // margin, not the transform: MapLibre rewrites the transform on every frame to
  // place the marker, and would drop an offset written there.
  const MARKER_CSS='width:28px;height:28px;border-radius:50%;background:#fff;color:#263238;border:3px solid #455a64;box-shadow:0 1px 5px rgba(0,0,0,.3);display:flex;align-items:center;justify-content:center;font:700 13px/1 Arial,sans-serif;box-sizing:border-box';
  function markerElement(content,offset=0){
    const element=document.createElement('div');
    element.style.cssText=MARKER_CSS+(offset?`;margin-left:${offset*20}px`:'');
    if(typeof content==='string')element.textContent=content;
    else if(content)element.append(content);
    return element;
  }
  // The route is drawn on Home Assistant's own <ha-map>. There is no second engine
  // and no fallback: if the map cannot be opened the card says so instead of quietly
  // swapping in a different one, because the card's whole point is to follow the
  // map settings the dashboard already uses.
  // Home Assistant only registers <ha-map> once something needs it. A dashboard
  // with no map card of its own may never define it, so a single lookup is not
  // enough: the card waits to see whether it turns up before giving up. Should it
  // appear later, the next refresh picks it up on its own.
  function haMapDefined(){
    if(customElements.get('ha-map'))return Promise.resolve(true);
    return Promise.race([
      customElements.whenDefined('ha-map').then(()=>true),
      new Promise(resolve=>setTimeout(()=>resolve(false),8000)),
    ]);
  }
  async function createSurface(card, container){
    if(!await haMapDefined())return {surface:null,note:'Карта Home Assistant недоступна. Обновите интерфейс Home Assistant.'};
    const haMap=document.createElement('ha-map');
    if(card._hass)haMap.hass=card._hass;
    container.append(haMap);
    try{
      const ml=await loadMapLibre();
      // <ha-map> builds its map in firstUpdated, so getMap() is the supported way
      // in and it may hand back nothing until it is ready. Either way the card has
      // to end up with a real map: without one the route cannot be drawn, and
      // drawing onto it would throw instead of saying so.
      let map=null;
      for(let attempt=0;attempt<40&&!map;attempt++){
        if(typeof haMap.getMap==='function')map=await haMap.getMap();
        if(!map)map=haMap.map||haMap._map||null;
        if(map)break;
        await new Promise(resolve=>setTimeout(resolve,150));
      }
      if(!map||typeof map.addSource!=='function')throw new Error('ha-map did not hand over a map');
      return {surface:createHaMapSurface(card, haMap, map, ml)};
    }catch(error){
      haMap.remove();
      console.warn('GWM Jolion trips card: Home Assistant map unavailable',error);
      return {surface:null,note:'Не удалось открыть карту Home Assistant. Пробег и выбор периода ниже работают.'};
    }
  }
  function createHaMapSurface(card, haMap, map, ml){
    const surface={engine:'ha', map, _haMap:haMap, _ml:ml, _seq:0, _cursor:null, _markers:[], _lines:[], _coords:[]};
    const removeLine=id=>{try{map.removeLayer(id);}catch{}try{map.removeSource(id);}catch{};};
    const removeCursor=()=>{surface._cursor?.remove();surface._cursor=null;};
    surface.destroy=()=>{surface.clear();surface._haMap?.remove();surface.map=null;};
    surface.clear=()=>{surface._lines.forEach(removeLine);surface._lines=[];surface._markers.forEach(m=>m.remove());surface._markers=[];removeCursor();surface._coords=[];};
    surface.hasOverlays=()=>!!(surface._lines.length||surface._markers.length||surface._coords.length);
    surface.addLine=(coords,{color,weight=4,opacity=1,dashArray=null,tooltip=null}={})=>{
      const id=`gwm-route-${surface._seq++}`;
      map.addSource(id,{type:'geojson',data:{type:'Feature',geometry:{type:'LineString',coordinates:coords.map(([lat,lng])=>[lng,lat])}}});
      const paint={'line-color':color,'line-width':weight,'line-opacity':opacity};
      if(dashArray)paint['line-dasharray']=dashArray.split(' ').map(Number);
      map.addLayer({id,type:'line',source:id,layout:{'line-cap':'round','line-join':'round'},paint});
      surface._lines.push(id);
      for(const [lat,lng] of coords)surface._coords.push([lat,lng]);
      if(tooltip!=null){
        const popup=new ml.Popup({offset:12,closeButton:false,closeOnClick:false}).setText(String(tooltip));
        map.on('mouseenter',id,event=>popup.setLngLat(event.lngLat).addTo(map));
        map.on('mouseleave',id,()=>popup.remove());
      }
    };
    surface.addMarker=(latlng,{iconElement,tooltip=null})=>{
      const marker=new ml.Marker({element:iconElement}).setLngLat([latlng[1],latlng[0]]).addTo(map);
      if(tooltip!=null){
        const popup=new ml.Popup({offset:30,closeButton:false,closeOnClick:false});
        if(typeof tooltip==='string')popup.setText(tooltip);else popup.setDOMContent(tooltip);
        marker.setPopup(popup);
      }
      surface._markers.push(marker);surface._coords.push(latlng);
    };
    surface.addCursor=latlng=>{
      removeCursor();
      const element=document.createElement('div');
      element.style.cssText='width:14px;height:14px;border-radius:50%;background:#039ecc;border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.4)';
      surface._cursor=new ml.Marker({element}).setLngLat([latlng[1],latlng[0]]).addTo(map);
    };
    surface.fitOverlays=()=>{
      if(!surface._coords.length)return;
      let minLat=Infinity,minLng=Infinity,maxLat=-Infinity,maxLng=-Infinity;
      for(const [lat,lng] of surface._coords){minLat=Math.min(minLat,lat);maxLat=Math.max(maxLat,lat);minLng=Math.min(minLng,lng);maxLng=Math.max(maxLng,lng);}
      map.fitBounds([[minLng,minLat],[maxLng,maxLat]],{padding:25,maxZoom:16});
    };
    surface.resetView=()=>map.jumpTo({center:[0,20],zoom:2});
    surface.flyTo=(latlng,zoom)=>map.flyTo({center:[latlng[1],latlng[0]],zoom,duration:450});
    surface.panTo=latlng=>map.panTo([latlng[1],latlng[0]]);
    surface.resize=()=>map.resize();
    return surface;
  }
  class TripsCard extends HTMLElement {
    static getConfigElement() { return document.createElement('gwm-jolion-trips-card-editor'); }
    static getStubConfig(hass) {
      return {entity: Object.keys(hass.states).find(id => id.startsWith('device_tracker.') && id.endsWith('_location')) || '', title:'Поездки',speed_green_max:80,speed_red_min:110};
    }
    constructor() {
      super(); this.attachShadow({mode:'open'}); this._mode='today'; this._serial=0;
      this.shadowRoot.innerHTML = `<link rel="stylesheet" href="/gwm-jolion/maplibre/maplibre-gl.css">
      <style>
        :host(.fallback-fullscreen) .playback,ha-card:fullscreen .playback{display:none}
        :host{display:block}ha-card{overflow:hidden}.content{padding:10px 14px 12px}
        .shortcuts,.dates,.summary{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
        button,input{font:inherit;font-size:13px;color:var(--primary-text-color);border:0;border-radius:10px;background:var(--secondary-background-color,#eee);padding:7px 11px;box-sizing:border-box}
        button{cursor:pointer}button.active{background:var(--primary-color,#03a9f4);color:white;border-color:transparent}
        button:focus-visible,input:focus-visible{outline:2px solid var(--primary-color,#03a9f4);outline-offset:2px}
        .dates{margin:10px 0 0}.dates[hidden]{display:none}label{display:flex;flex:1;min-width:110px;flex-direction:column;gap:5px;color:var(--secondary-text-color);font-size:12px}input{width:100%;color-scheme:light dark}
        .summary{justify-content:center;margin:0 0 8px;gap:8px}.km{font-size:26px;font-weight:600;font-variant-numeric:tabular-nums}.summary ha-icon{color:var(--secondary-text-color);--mdc-icon-size:22px}.shortcuts{justify-content:center;flex-wrap:nowrap;gap:6px}#calendar{display:flex;align-items:center;justify-content:center;width:34px;height:32px;padding:0}#calendar ha-icon{--mdc-icon-size:19px}
        .error,.map-status{color:var(--secondary-text-color);font-size:12px;text-align:center}.error:empty,.map-status:empty{display:none}.error:not(:empty),.map-status:not(:empty){margin-top:8px}.map-wrap{position:relative;height:300px;background:#e9edef}.map{height:100%;background:#e9edef;z-index:0}
        .map-actions{position:absolute;top:8px;right:8px;z-index:1000;display:flex;gap:6px}.map-actions button{display:flex;align-items:center;justify-content:center;width:34px;height:34px;padding:0;background:var(--card-background-color,#fff);box-shadow:0 1px 5px rgba(0,0,0,.28)}.map-actions ha-icon{--mdc-icon-size:19px}
        :host(.fallback-fullscreen){position:fixed;inset:0;z-index:1000;display:block;background:var(--card-background-color,#fff)}:host(.fallback-fullscreen) ha-card,ha-card:fullscreen{width:100%;height:100%;min-height:100%;display:flex;flex-direction:column;border-radius:0;background:var(--card-background-color,#fff)}:host(.fallback-fullscreen) .map-wrap,ha-card:fullscreen .map-wrap{flex:1;height:auto;min-height:0}:host(.fallback-fullscreen) .content,ha-card:fullscreen .content{display:none}
        @media(max-width:350px){button{padding:7px 8px}.content{padding:10px}.map-wrap{height:260px}}
      </style><ha-card><div class="map-wrap"><div class="map" aria-label="Карта маршрута"></div><div class="map-actions"><button id="centerBtn" type="button" title="Показать автомобиль в центре карты" aria-label="Показать автомобиль в центре карты"><ha-icon icon="mdi:crosshairs-gps"></ha-icon></button><button id="fullscreenBtn" type="button" title="Развернуть карту" aria-label="Развернуть карту" aria-pressed="false"><ha-icon icon="mdi:fullscreen"></ha-icon></button></div></div><div class="content">
      <div class="summary"><ha-icon icon="mdi:counter" aria-hidden="true"></ha-icon><span class="km" aria-label="Пробег за выбранный период">—</span></div>
      <div class="shortcuts"><button data-mode="today">Сегодня</button><button data-mode="yesterday">Вчера</button><button data-mode="week">Неделя</button><button id="calendar" title="Выбрать период" aria-label="Выбрать период" aria-expanded="false" aria-controls="period"><ha-icon icon="mdi:calendar-range"></ha-icon></button></div>
      <div class="dates" id="period" hidden><label>С<input type="date" id="start"></label><label>По<input type="date" id="end"></label><button id="show">Выбрать</button></div>
      <div class="error" role="status"></div><div class="map-status" role="status"></div></div><div class="playback" style="padding:0 14px 12px" hidden><svg class="speed-chart" viewBox="0 0 600 55" style="width:100%;height:55px" aria-label="Скорость по времени"><path fill="none" stroke="#039ecc" stroke-width="2"></path></svg><input class="timeline" type="range" min="0" max="0" value="0" aria-label="Просмотр трека по времени" style="width:100%;box-sizing:border-box"><div class="selected" style="font-size:12px;text-align:center"></div></div></ha-card>`;
      this.shadowRoot.querySelector('.timeline').oninput=e=>this._selectPoint(Number(e.target.value));
      this._mapCard=this.shadowRoot.querySelector('ha-card');
      this._fullscreenBtn=this.shadowRoot.querySelector('#fullscreenBtn');
      this.shadowRoot.querySelector('#centerBtn').onclick=()=>this._centerVehicle();
      this._fullscreenBtn.onclick=()=>this._toggleFullscreen();
      this._onFullscreenChange=()=>{this._syncFullscreenButton();requestAnimationFrame(()=>this._surface?.resize());};
      this.shadowRoot.querySelectorAll('[data-mode]').forEach(button => button.onclick=()=>{this._mode=button.dataset.mode;this._calendar(false);this._load();});
      this.shadowRoot.querySelector('#show').onclick=()=>{const start=this.shadowRoot.querySelector('#start').value,end=this.shadowRoot.querySelector('#end').value;if(!start || !end || start>end){this.shadowRoot.querySelector('.error').textContent='Проверьте даты.';return;}this._mode='custom';this._range=[start,end];this._calendar(false);this._load();};
      this.shadowRoot.querySelector('#calendar').onclick=()=>this._calendar(this.shadowRoot.querySelector('.dates').hidden);
    }
    // The map itself, so the card's tests and any consumer can reach it directly.
    get _map(){return this._surface?.map ?? null;}
    _renderPlayback(data){
      this._points=data.playback || [];
      const root=this.shadowRoot,box=root.querySelector('.playback'),slider=root.querySelector('.timeline');
      box.hidden=!this._points.length;slider.max=String(Math.max(0,this._points.length-1));slider.value='0';slider.oninput=e=>this._selectPoint(Number(e.target.value));
      slider.title=data.playback_sample_step>1?'Для посекундного просмотра выберите один день':'Все записанные точки выбранного периода';
      const points=this._points, max=points.reduce((m,p)=>Math.max(m,p.speed_kmh||0),1),first=points[0]?.timestamp_ms,last=points.at(-1)?.timestamp_ms;
      let drawing='',gap=true;
      const stride=Math.max(1,Math.ceil(points.length/2000));
      points.forEach((p,i)=>{if(p.speed_kmh==null){gap=true;return;}if(p.display_break||(i&&p.timestamp_ms-points[i-1].timestamp_ms>120000))gap=true;if(i%stride&&i!==points.length-1)return;const x=(p.timestamp_ms-first)/Math.max(1,last-first)*600,y=53-p.speed_kmh/max*50;drawing+=`${gap?'M':'L'}${x.toFixed(1)},${y.toFixed(1)} `;gap=false;});
      root.querySelector('.speed-chart path').setAttribute('d',drawing);this._cursor?.remove();this._cursor=null;
      root.querySelector('.selected').textContent=points.length?'Выберите точку трека':'';
      if(this._selectedTime!=null && points.length){
        let low=0,high=points.length;
        while(low<high){const mid=(low+high)>>1;if(points[mid].timestamp_ms<this._selectedTime)low=mid+1;else high=mid;}
        let index=Math.min(low,points.length-1);
        if(index>0&&Math.abs(points[index-1].timestamp_ms-this._selectedTime)<Math.abs(points[index].timestamp_ms-this._selectedTime))index--;
        this._selectPoint(index,false);
      }
    }
    _selectPoint(index,pan=true){
      const p=this._points?.[index];if(!p||!this._surface?.map)return;
      this._selectedTime=p.timestamp_ms;this.shadowRoot.querySelector('.timeline').value=String(index);
      const text=new Intl.DateTimeFormat('ru-RU',{timeZone:this._hass.config.time_zone,day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit'}).format(new Date(p.timestamp_ms));
      this.shadowRoot.querySelector('.selected').textContent=`${text} · ${p.speed_kmh==null?'скорость неизвестна':`${p.speed_estimated?'≈ ':''}${Math.round(p.speed_kmh)} км/ч`} · ${p.source==='app'?'GPS приложения':'облако'}${p.accuracy_m!=null?` · GPS ±${Math.round(p.accuracy_m)} м`:''}${p.source==='app'?` · погрешность скорости: ${p.speed_accuracy_kmh==null?'неизвестна':`±${Number(p.speed_accuracy_kmh.toFixed(1))} км/ч`}`:''}${p.display_filtered?' · сглажено':''}`;
      this._surface.addCursor([p.latitude,p.longitude]);if(pan)this._surface.panTo([p.latitude,p.longitude]);
    }
    setConfig(config) {
      this._config={...config}; this._serial++;this._fitKey=null;
      this.setAttribute('aria-label',config.title || 'Поездки');
      this._surface?.clear(); this._load();
    }
    set hass(hass) {
      const first=!this._hass; this._hass=hass;
      // <ha-map> reads its theme and entities off hass, so it has to be handed the
      // current one, not the one that happened to arrive when the map was created.
      if(this._surface?._haMap)this._surface._haMap.hass=hass;
      if(first) this._load();
    }
    connectedCallback() {
      clearInterval(this._timer); this._timer=setInterval(()=>this._load(),60000);
      document.addEventListener('fullscreenchange',this._onFullscreenChange);
      this._resize=new ResizeObserver(()=>this._surface?.resize());this._resize.observe(this);
      this._load();
    }
    disconnectedCallback(){ clearInterval(this._timer);this._resize?.disconnect();document.removeEventListener('fullscreenchange',this._onFullscreenChange);this.classList.remove('fallback-fullscreen');if(document.fullscreenElement===this._mapCard&&document.exitFullscreen)document.exitFullscreen().catch(()=>{});this._serial++;this._surface?.destroy();this._surface=null;this._fitKey=null; }
    getCardSize(){return 6;}
    _calendar(open){this.shadowRoot.querySelector('.dates').hidden=!open;this.shadowRoot.querySelector('#calendar').setAttribute('aria-expanded',String(open));if(open)this.shadowRoot.querySelector('#start').focus();}
    _highlight(){this.shadowRoot.querySelectorAll('[data-mode]').forEach(b=>b.classList.toggle('active',b.dataset.mode===this._mode));this.shadowRoot.querySelector('#calendar').classList.toggle('active',this._mode==='custom');}
    _centerVehicle(){
      const state=this._hass?.states[this._config?.entity];
      const latitude=Number(state?.attributes.latitude),longitude=Number(state?.attributes.longitude);
      if(!this._surface?.map)return;
      if(Number.isFinite(latitude)&&Number.isFinite(longitude))this._surface.flyTo([latitude,longitude],Math.max(this._surface.map.getZoom(),16));
      else if(this._surface.hasOverlays())this._surface.fitOverlays();
    }
    async _toggleFullscreen(){
      if(this.classList.contains('fallback-fullscreen')){this._setFallbackFullscreen(false);return;}
      if(document.fullscreenElement===this._mapCard){if(document.exitFullscreen)await document.exitFullscreen();return;}
      if(this._mapCard.requestFullscreen){
        try{await this._mapCard.requestFullscreen({navigationUI:'hide'});return;}catch{}
      }
      this._setFallbackFullscreen(true);
    }
    _setFallbackFullscreen(active){this.classList.toggle('fallback-fullscreen',active);this._syncFullscreenButton();requestAnimationFrame(()=>this._surface?.resize());}
    _syncFullscreenButton(){
      const active=this.classList.contains('fallback-fullscreen')||document.fullscreenElement===this._mapCard;
      this._fullscreenBtn.setAttribute('aria-pressed',String(active));
      this._fullscreenBtn.setAttribute('aria-label',active?'Свернуть карту':'Развернуть карту');
      this._fullscreenBtn.title=active?'Свернуть карту':'Развернуть карту';
      this._fullscreenBtn.querySelector('ha-icon').setAttribute('icon',active?'mdi:fullscreen-exit':'mdi:fullscreen');
    }
    async _load(){
      if(!this.isConnected || !this._hass || !this._config)return;
      const serial=++this._serial;
      const root=this.shadowRoot, error=root.querySelector('.error');
      if(!this._config.entity){error.textContent='Выберите сущность местоположения GWM Jolion в настройках карточки.';return;}
      const today=dateInZone(this._hass.config.time_zone);
      if(!root.querySelector('.dates').hidden && this._fitKey)return;
      if(this._mode==='custom' && this._range){root.querySelector('#start').value=this._range[0];root.querySelector('#end').value=this._range[1];}
      else if(this._mode!=='custom'){
        root.querySelector('#end').value=this._mode==='yesterday'?shift(today,-1):today;
        root.querySelector('#start').value=this._mode==='week'?shift(today,-6):root.querySelector('#end').value;
      }
      const start=root.querySelector('#start').value,end=root.querySelector('#end').value;
      this._highlight();
      if(!start || !end || start>end){error.textContent='Проверьте начало и конец периода.';return;}
      const queryKey=`${this._config.entity}|${this._config.odometer_entity || ''}|${start}|${end}`;
      if(this._queryKey!==queryKey){this._selectedTime=null;this._renderPlayback({playback:[]});this._surface?.clear();root.querySelector('.km').textContent='—';this._queryKey=queryKey;}
      error.textContent='';root.querySelector('.summary').setAttribute('aria-busy','true');
      let timeout;
      try{
        const data=await Promise.race([this._hass.callWS({type:'gwm_jolion/trips',entity_id:this._config.entity,start,end,...(this._config.odometer_entity?{odometer_entity:this._config.odometer_entity}:{})}),new Promise((_,reject)=>{timeout=setTimeout(()=>reject(new Error('Не удалось загрузить историю. Выберите период ещё раз.')),20000);})]);
        if(serial!==this._serial || !this.isConnected)return;
        error.textContent=data.samples?'':'За этот период нет записей.';
        root.querySelector('.km').textContent=data.samples?`${data.method==='odometer'?'':'≈ '}${data.km.toLocaleString('ru-RU')}`:'—';
        root.querySelector('.km').title=`${start} — ${end} · км${data.method==='odometer'?'':' · оценка'}`;
        if(!this._surface){
          const {surface,note}=await createSurface(this,root.querySelector('.map'));
          if(serial!==this._serial || !this.isConnected){surface?.destroy();return;}
          this._surface=surface;this._fitKey=null;
          if(note)root.querySelector('.map-status').textContent=note;
        }
        if(!this._surface)return;
        this._surface.clear();this._renderPlayback(data);
        for(const gap of data.gaps || [])this._surface.addLine(gap,{color:'#88949f',weight:2,dashArray:'5 7',opacity:.7,tooltip:'Нет GPS-данных: связь между точками, не записанный маршрут'});
        const speedSegments=Array.isArray(data.segment_speeds_kmh)?data.segment_speeds_kmh:[];
        const speedKinds=Array.isArray(data.segment_kinds)?data.segment_kinds:[];
        const parkingSpots=Array.isArray(data.parking_spots)?data.parking_spots:[];
        const hasSpeeds=speedSegments.length===data.segments.length;
        const limits=speedLimits(this._config);
        for(const [segmentIndex,segment] of data.segments.entries()){
          if(!hasSpeeds){if(segment.length>1)this._surface.addLine(simplifyPath(segment),{color:'#009fce',weight:4,opacity:.85});continue;}
          const speeds=speedSegments[segmentIndex]||[],kinds=speedKinds[segmentIndex]||[];
          const runs=stationaryRuns(segment,kinds);
          // Consecutive pieces of the same speed were drawn one line per GPS
          // pair, so every join showed as a hard step. Gather each run of one
          // colour into a single line, so the map joins them with round caps.
          let run=[],runColor=null,runSpeed=0;
          const flush=()=>{
            if(run.length>1)this._surface.addLine(simplifyPath(run),{color:runColor,weight:4,opacity:.9,tooltip:`Средняя скорость: ${Math.round(runSpeed)} км/ч`});
            run=[];runColor=null;
          };
          for(let index=1;index<segment.length;index++){
            const rawSpeed=speeds[index-1],speed=Number(rawSpeed);
            if(kinds[index-1]==='stationary'){
              flush();
              const run=runs.get(index);
              if(run&&run.points.length>1){
                // Always drawn: dropping these segments tore holes in the track at
                // every stop. The wander is softened instead - one thin dashed line
                // per run rather than a solid grey line per GPS pair, so it stops
                // reading as a road without taking the route with it.
                this._surface.addLine(simplifyPath(run.points),{color:'#88949f',weight:2,opacity:.45,dashArray:'2 6',tooltip:'Замедленное движение по записанным GPS-точкам'});
                index=run.end;
              }
              continue;
            }
            if(kinds[index-1]==='unknown'||rawSpeed===null||rawSpeed===undefined||!Number.isFinite(speed)||speed<=0){flush();continue;}
            const color=speed<limits.green?SPEED_COLORS.low:speed<limits.red?SPEED_COLORS.medium:SPEED_COLORS.high;
            if(color!==runColor){flush();runColor=color;runSpeed=speed;run=[segment[index-1]];}
            else runSpeed=Math.round((runSpeed+speed)/2);
            run.push(segment[index]);
          }
          flush();
        }
        const parkingOccurrencesForPeriod=parkingOccurrences(parkingSpots,start,end,this._hass.config.time_zone),multiDay=start!==end;
        for(const parking of parkingOccurrencesForPeriod){
          const latitude=Number(parking.latitude),longitude=Number(parking.longitude),parkingStart=Number(parking.start),parkingEnd=parking.end===null||parking.end===undefined?NaN:Number(parking.end);
          if(!Number.isFinite(latitude)||!Number.isFinite(longitude)||!Number.isFinite(parkingStart))continue;
          const showDates=multiDay||dayInZone(parkingStart,this._hass.config.time_zone)!==parking.day||(Number.isFinite(parkingEnd)&&dayInZone(parkingStart,this._hass.config.time_zone)!==dayInZone(parkingEnd,this._hass.config.time_zone));
          const label=document.createElement('div');label.style.whiteSpace='pre-line';
          const inferredNote=parking.inferred?(parking.inferred_by==='odometer'?'\nПробег не менялся: стоянка выведена по молчанию и пробегу.':'\nПробег рядом недоступен: стоянка выведена по молчанию и координатам.'):'';
          label.textContent=`Стоянка ${parking.label}${parking.inferred?'*':''}\nНачало: ${tripTime(parkingStart,this._hass.config.time_zone,showDates)}${parking.show_end?`\nКонец: ${tripTime(parkingEnd,this._hass.config.time_zone,showDates)}`:''}${inferredNote}`;
          for(const gap of parking.interruptions || [])label.textContent+=`\nНет данных: ${tripTime(gap[0],this._hass.config.time_zone,true)} — ${tripTime(gap[1],this._hass.config.time_zone,true)}`;
          // The star is explained in full in the popup: with the legend gone from
          // under the map, the tooltip is the only place the reader learns that a
          // stop marked with one was inferred rather than measured.
          this._surface.addMarker([latitude,longitude],{iconElement:markerElement(parking.label+(parking.inferred?'*':''),parking.offset_index),tooltip:label});
        }
        if(!this._surface.hasOverlays() && start<=today && today<=end){
          const validPosition=value=>value && value.latitude!==null && value.longitude!==null && value.latitude!=='' && value.longitude!=='' && Number.isFinite(Number(value.latitude)) && Number.isFinite(Number(value.longitude)) && Math.abs(Number(value.latitude))<=90 && Math.abs(Number(value.longitude))<=180 && (Number(value.latitude)!==0 || Number(value.longitude)!==0);
          const current=this._hass.states[this._config.entity]?.attributes;
          const filtered=current?.golion_locator_enabled && validPosition(data.last_position);
          const position=filtered?data.last_position:validPosition(current)?current:validPosition(data.last_position)?data.last_position:null;
          if(position){
            const icon=document.createElement('ha-icon');icon.setAttribute('icon','mdi:car');
            this._surface.addMarker([Number(position.latitude),Number(position.longitude)],{iconElement:markerElement(icon),tooltip:'Последнее известное положение автомобиля'});
          }
        }
        if(this._surface.hasOverlays()){this._surface.resize();const key=`${this._config.entity}|${start}|${end}`;if(this._fitKey!==key){this._surface.fitOverlays();this._fitKey=key;}}
        else {this._surface.resetView();this._fitKey=null;}
      }catch(err){if(serial===this._serial)error.textContent=err.message || 'Не удалось загрузить историю. Проверьте выбранную сущность.';}
      finally{clearTimeout(timeout);if(serial===this._serial)root.querySelector('.summary').setAttribute('aria-busy','false');}
    }
  }
  class TripsEditor extends HTMLElement{
    setConfig(config){
      this._config=config;const limits=speedLimits(config);
      for(const [key,field] of Object.entries(this._fields || {})){
        field.value=key==='speed_green_max'?limits.green:key==='speed_red_min'?limits.red:config[key] || '';
      }
      this._render();
    }
    set hass(value){this._hass=value;for(const field of Object.values(this._fields || {}))field.hass=value;this._render();}
    _render(){if(!this._config || !this._hass || this._fields)return;this._fields={};
      for(const [key,domain,title] of [['entity','device_tracker','Местоположение автомобиля'],['odometer_entity','sensor','Пробег (необязательно, определяется автоматически)']]){
        const label=document.createElement('label');label.textContent=title;
        const field=document.createElement('ha-selector');field.hass=this._hass;field.selector={entity:{domain}};field.value=this._config[key] || '';field.style.display='block';field.style.marginBottom='16px';this._fields[key]=field;
        field.addEventListener('value-changed',e=>{this._config={...this._config,[key]:e.detail.value || ''};this.dispatchEvent(new CustomEvent('config-changed',{detail:{config:this._config},bubbles:true,composed:true}));});this.append(label,field);
      }
      // No map selector: the route is drawn on Home Assistant's own map, which
      // already uses whatever the dashboard is set to. A second choice here could
      // only contradict that.
      const section=document.createElement('div');section.textContent='Диапазоны цветов скорости';section.style.cssText='font-weight:600;margin:4px 0 12px';this.append(section);
      const limits=speedLimits(this._config);
      for(const [key,title] of [['speed_green_max','Зелёный: до, км/ч'],['speed_red_min','Красный: от, км/ч']]){
        const speedLabel=document.createElement('label');speedLabel.textContent=title;
        const speedField=document.createElement('ha-selector');speedField.hass=this._hass;speedField.selector={number:{min:1,max:300,step:1,mode:'box',unit_of_measurement:'км/ч'}};speedField.value=key==='speed_green_max'?limits.green:limits.red;speedField.style.display='block';speedField.style.marginBottom='16px';this._fields[key]=speedField;
        speedField.addEventListener('value-changed',event=>{const next=speedLimits({...this._config,[key]:event.detail.value});this._config={...this._config,speed_green_max:next.green,speed_red_min:next.red};this._fields.speed_green_max.value=next.green;this._fields.speed_red_min.value=next.red;this.dispatchEvent(new CustomEvent('config-changed',{detail:{config:this._config},bubbles:true,composed:true}));});this.append(speedLabel,speedField);
      }
    }
  }
  if(!customElements.get('gwm-jolion-trips-card'))customElements.define('gwm-jolion-trips-card',TripsCard);
  if(!customElements.get('gwm-jolion-trips-card-editor'))customElements.define('gwm-jolion-trips-card-editor',TripsEditor);
  window.customCards=window.customCards || [];window.customCards.push({type:'gwm-jolion-trips-card',name:'GWM Jolion — Поездки',description:'Карта маршрута и пробег за день или период',preview:true});
})();


