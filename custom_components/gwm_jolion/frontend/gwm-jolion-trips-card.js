/* GWM Jolion Trips Card v0.2.1 */
(() => {
  let leaflet;
  const STYLES = {positron:'Светлая · OpenFreeMap',dark:'Тёмная · OpenFreeMap',liberty:'Стандартная · OpenFreeMap',osm:'OpenStreetMap'};
  const SPEED_COLORS = {low:'#2e7d32',medium:'#f9a825',high:'#c62828'};
  const TRIP_COLORS=['#2563eb','#9333ea','#0891b2','#ea580c','#db2777','#0d9488','#6366f1','#a16207'];
  const DEFAULT_SPEED_LIMITS = {green:80,red:110};
  function speedLimits(config={}){
    const limit=(value,fallback)=>{const number=Number(value);return value!==null&&value!==undefined&&value!==''&&Number.isFinite(number)?Math.max(1,Math.min(300,Math.round(number))):fallback;};
    let green=limit(config.speed_green_max,DEFAULT_SPEED_LIMITS.green),red=limit(config.speed_red_min,DEFAULT_SPEED_LIMITS.red);
    if(green>=300)green=299;
    if(red<=green)red=Math.min(300,green+1);
    return {green,red};
  }
  let vectorMaps;
  function loadScript(src){return new Promise((resolve,reject)=>{
    const script=document.createElement('script');const timer=setTimeout(()=>{script.remove();reject(new Error('Не удалось загрузить оформление карты'));},15000);
    script.src=src;script.onload=()=>{clearTimeout(timer);resolve();};script.onerror=()=>{clearTimeout(timer);script.remove();reject(new Error('Не удалось загрузить оформление карты'));};document.head.append(script);
  });}
  function loadVector(L){return vectorMaps ||= (async()=>{
    window.GwmTripsLeaflet=L;
    if(!window.GwmTripsMapLibre){const previous=window.maplibregl;await loadScript('/gwm-jolion/maplibre/maplibre-gl.js');window.GwmTripsMapLibre=window.maplibregl;window.maplibregl=previous;}
    if(!L.maplibreGL)await loadScript('/gwm-jolion/maplibre/leaflet-maplibre-gl.js');
  })().catch(error=>{vectorMaps=null;throw error;});}
  const loadMap = () => leaflet ||= new Promise((resolve, reject) => {
    const script = document.createElement('script');
    const timer = setTimeout(() => { script.remove(); leaflet = null; reject(new Error('Не удалось загрузить карту')); }, 15000);
    script.src = '/gwm-jolion/leaflet/leaflet.js';
    script.onload = () => { clearTimeout(timer); resolve(window.L.noConflict()); };
    script.onerror = () => { clearTimeout(timer); script.remove(); leaflet = null; reject(new Error('Не удалось загрузить карту')); };
    document.head.append(script);
  });
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
  function routeGpx(data,start,end){
    const segments=[];
    for(const [s,points] of (data.segments||[]).entries()){
      let run=[];
      const flush=()=>{if(run.length)segments.push(`    <trkseg>\n${run.join('\n')}\n    </trkseg>`);run=[];};
      for(const [i,point] of points.entries()){
        const [lat,lon]=point||[];
        if(!Number.isFinite(lat)||!Number.isFinite(lon)||Math.abs(lat)>90||Math.abs(lon)>180){flush();continue;}
        const stamp=data.segment_timestamps?.[s]?.[i],date=Number.isFinite(stamp)?new Date(stamp*1000):null;
        const time=date&&Number.isFinite(date.getTime())?`<time>${date.toISOString()}</time>`:'';
        run.push(`      <trkpt lat="${lat}" lon="${lon}">${time}</trkpt>`);
      }
      flush();
    }
    if(!segments.length)return null;
    const escape=value=>String(value).replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&apos;'}[char]));
    return `<?xml version="1.0" encoding="UTF-8"?>\n<gpx version="1.1" creator="GWM Jolion" xmlns="http://www.topografix.com/GPX/1/1">\n  <trk>\n    <name>${escape(`Jolion ${start} — ${end}`)}</name>\n${segments.join('\n')}\n  </trk>\n</gpx>\n`;
  }
  function parkingOccurrences(spots,start,end,zone,firstIndex=0){let sequence=firstIndex;const spotOffsets={};return spots.flatMap(spot=>{const started=Number(spot.start),ended=spot.end===null||spot.end===undefined?NaN:Number(spot.end),startDay=dayInZone(started,zone),endDay=dayInZone(Number.isFinite(ended)?ended:Number(spot.observed_until ?? (started+Number(spot.duration || 0))),zone),spotKey=`${spot.latitude}|${spot.longitude}|${spot.start}|${spot.end}`;return dateRange(start,end).filter(day=>startDay<=day&&(!endDay||day<=endDay)).map(day=>{const index=sequence++,offset=spotOffsets[spotKey]||0;spotOffsets[spotKey]=offset+1;return {...spot,day,label:pointLabel(index),offset_index:offset,show_end:Number.isFinite(ended)&&day===endDay};});});}
  class TripsCard extends HTMLElement {
    static getConfigElement() { return document.createElement('gwm-jolion-trips-card-editor'); }
    static getStubConfig(hass) {
      return {entity: Object.keys(hass.states).find(id => id.startsWith('device_tracker.') && id.endsWith('_location')) || '', title:'Поездки',map_style:'positron',speed_green_max:80,speed_red_min:110};
    }
    constructor() {
      super(); this.attachShadow({mode:'open'}); this._mode='today'; this._serial=0;
      this.shadowRoot.innerHTML = `<link rel="stylesheet" href="/gwm-jolion/leaflet/leaflet.css">
      <link rel="stylesheet" href="/gwm-jolion/maplibre/maplibre-gl.css">
      <style>
        :host{display:block}ha-card{overflow:hidden}.content{padding:10px 14px 12px}
        .shortcuts,.dates,.summary{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
        button,input{font:inherit;font-size:13px;color:var(--primary-text-color);border:0;border-radius:10px;background:var(--secondary-background-color,#eee);padding:7px 11px;box-sizing:border-box}
        button{cursor:pointer}button.active{background:var(--primary-color,#03a9f4);color:white;border-color:transparent}
        button:focus-visible,input:focus-visible{outline:2px solid var(--primary-color,#03a9f4);outline-offset:2px}
        .dates{margin:10px 0 0}.dates[hidden]{display:none}label{display:flex;flex:1;min-width:110px;flex-direction:column;gap:5px;color:var(--secondary-text-color);font-size:12px}input{width:100%;color-scheme:light dark}
        .summary{justify-content:center;margin:0 0 8px;gap:8px}.km{font-size:26px;font-weight:600;font-variant-numeric:tabular-nums}.summary ha-icon{color:var(--secondary-text-color);--mdc-icon-size:22px}.shortcuts{justify-content:center;flex-wrap:nowrap;gap:6px}#calendar{display:flex;align-items:center;justify-content:center;width:34px;height:32px;padding:0}#calendar ha-icon{--mdc-icon-size:19px}
        .speed-legend{display:flex;justify-content:center;gap:12px;flex-wrap:wrap;margin:0 0 10px;color:var(--secondary-text-color);font-size:11px}.speed-legend[hidden]{display:none}.speed-legend span{display:flex;align-items:center;gap:4px}.speed-legend i{width:10px;height:4px;border-radius:2px;background:#888}.speed-legend b{font-weight:400}.speed-legend .low{background:#2e7d32}.speed-legend .medium{background:#f9a825}.speed-legend .high{background:#c62828}
        .route-point{width:28px;height:28px;border-radius:50%;background:#fff;color:#263238;border:3px solid #455a64;box-shadow:0 1px 5px rgba(0,0,0,.3);display:flex;align-items:center;justify-content:center;font:700 13px/1 Arial,sans-serif;box-sizing:border-box}
        .error,.map-status{color:var(--secondary-text-color);font-size:12px;text-align:center}.error:empty,.map-status:empty{display:none}.error:not(:empty),.map-status:not(:empty){margin-top:8px}.map-wrap{position:relative;height:300px;background:#e9edef}.map{height:100%;background:#e9edef;z-index:0}
        .map-actions{position:absolute;top:8px;right:8px;z-index:1000;display:flex;gap:6px}.map-actions button{display:flex;align-items:center;justify-content:center;width:34px;height:34px;padding:0;background:var(--card-background-color,#fff);box-shadow:0 1px 5px rgba(0,0,0,.28)}.map-actions ha-icon{--mdc-icon-size:19px}
        :host(.fallback-fullscreen){position:fixed;inset:0;z-index:1000;display:block;background:var(--card-background-color,#fff)}:host(.fallback-fullscreen) ha-card,ha-card:fullscreen{width:100%;height:100%;min-height:100%;display:flex;flex-direction:column;border-radius:0;background:var(--card-background-color,#fff)}:host(.fallback-fullscreen) .map-wrap,ha-card:fullscreen .map-wrap{flex:1;height:auto;min-height:0}:host(.fallback-fullscreen) .content,ha-card:fullscreen .content{display:none}
        .leaflet-container{font-family:inherit}.leaflet-control-attribution{font-size:10px}
        .trip-navigation{position:absolute;bottom:24px;left:10px;right:10px;z-index:1000;display:flex;align-items:center;gap:8px;flex-wrap:wrap;pointer-events:none}.trip-navigation button,.trip-navigation span{pointer-events:auto;background:var(--card-background-color,#fff);box-shadow:0 2px 9px #0003;padding:9px 12px;border-radius:12px;font-size:12px}.trip-navigation [hidden]{display:none}.trip-navigation span{max-width:100%;box-sizing:border-box}.route-hit{cursor:pointer}
        @media(max-width:350px){button{padding:7px 8px}.content{padding:10px}.map-wrap{height:260px}}
      </style><ha-card><div class="map-wrap"><div class="map" aria-label="Карта маршрута"></div><div class="map-actions"><button id="centerBtn" type="button" title="Показать автомобиль в центре карты" aria-label="Показать автомобиль в центре карты"><ha-icon icon="mdi:crosshairs-gps"></ha-icon></button><button id="fullscreenBtn" type="button" title="Развернуть карту" aria-label="Развернуть карту" aria-pressed="false"><ha-icon icon="mdi:fullscreen"></ha-icon></button></div></div><div class="content">
      <div class="speed-legend" aria-label="Цвета средней скорости" hidden><span><i class="low"></i><b class="low-range">до 80 км/ч</b></span><span><i class="medium"></i><b class="medium-range">80–110 км/ч</b></span><span><i class="high"></i><b class="high-range">110+ км/ч</b></span></div>
      <div class="summary"><ha-icon icon="mdi:counter" aria-hidden="true"></ha-icon><span class="km" aria-label="Пробег за выбранный период">—</span></div>
      <div class="shortcuts"><button data-mode="today">Сегодня</button><button data-mode="yesterday">Вчера</button><button data-mode="week">Неделя</button><button id="calendar" title="Выбрать период" aria-label="Выбрать период" aria-expanded="false" aria-controls="period"><ha-icon icon="mdi:calendar-range"></ha-icon></button></div>
      <div class="dates" id="period" hidden><label>С<input type="date" id="start"></label><label>По<input type="date" id="end"></label><button id="show">Выбрать</button></div>
      <div class="error" role="status"></div><div class="map-status" role="status"></div><div class="diagnostics" role="status" hidden></div></div></ha-card>`;
      this._mapCard=this.shadowRoot.querySelector('ha-card');
      const navigation=document.createElement('div');navigation.className='trip-navigation';
      navigation.innerHTML='<button type="button" class="all-trips" hidden>← Весь трек</button><span class="trip-caption" role="status" hidden></span>';
      this.shadowRoot.querySelector('.map-wrap').append(navigation);
      navigation.querySelector('button').onclick=()=>this._selectTrip(null);
      const exportButton=document.createElement('button');exportButton.type='button';exportButton.textContent='Скачать точки';exportButton.title='JSON текущего периода содержит точные координаты для разбора ошибок маршрута';
      exportButton.onclick=()=>{
        if(!this._routeContext)return;
        const {data,start,end}=this._routeContext;
        const url=URL.createObjectURL(new Blob([JSON.stringify({schema:1,start,end,data},null,2)],{type:'application/json'}));
        const link=document.createElement('a');link.href=url;link.download=`jolion-track-${start}-${end}.json`;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
      };navigation.append(exportButton);
      this._exportButton=exportButton;
      const gpxButton=document.createElement('button');gpxButton.type='button';gpxButton.className='download-gpx';gpxButton.textContent='Скачать GPX';gpxButton.title='Маршрут за весь выбранный период в формате GPX';gpxButton.hidden=true;gpxButton.disabled=true;
      gpxButton.onclick=()=>{
        if(!this._routeContext)return;
        const {data,start,end}=this._routeContext,gpx=routeGpx(data,start,end);
        if(!gpx)return;
        const url=URL.createObjectURL(new Blob([gpx],{type:'application/gpx+xml;charset=utf-8'}));
        const link=document.createElement('a');link.href=url;link.download=`jolion-track-${start}-${end}.gpx`;document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
      };navigation.append(gpxButton);this._gpxButton=gpxButton;
      const closeButton=document.createElement('button');closeButton.type='button';closeButton.textContent='✕ Закрыть карту';closeButton.hidden=true;closeButton.className='close-map';
      closeButton.style.cssText='min-height:48px;touch-action:manipulation';
      closeButton.onclick=()=>this._exitFullscreen();navigation.append(closeButton);this._closeMapButton=closeButton;
      navigation.style.bottom='calc(24px + env(safe-area-inset-bottom, 0px))';
      this.addEventListener('keydown',event=>{if(event.key==='Escape'&&this._selectedTrip!=null){event.stopPropagation();this._selectTrip(null);}});
      this._fullscreenBtn=this.shadowRoot.querySelector('#fullscreenBtn');
      this.shadowRoot.querySelector('#centerBtn').onclick=()=>this._centerVehicle();
      this._fullscreenBtn.onclick=()=>this._toggleFullscreen();
      this._onFullscreenChange=()=>{this._syncFullscreenButton();requestAnimationFrame(()=>this._map?.invalidateSize());};
      this.shadowRoot.querySelectorAll('[data-mode]').forEach(button => button.onclick=()=>{this._mode=button.dataset.mode;this._calendar(false);this._load();});
      this.shadowRoot.querySelector('#show').onclick=()=>{const start=this.shadowRoot.querySelector('#start').value,end=this.shadowRoot.querySelector('#end').value;if(!start || !end || start>end){this.shadowRoot.querySelector('.error').textContent='Проверьте даты.';return;}this._mode='custom';this._range=[start,end];this._calendar(false);this._load();};
      this.shadowRoot.querySelector('#calendar').onclick=()=>this._calendar(this.shadowRoot.querySelector('.dates').hidden);
    }
    setConfig(config) {
      this._config={...config}; this._serial++;this._fitKey=null;this._selectedTrip=null;this._overview=null;
      this._exportButton.hidden=config.show_download_points===false;
      this._gpxButton.hidden=config.show_download_gpx!==true;
      this._routeContext=null;this._gpxButton.disabled=true;
      this.setAttribute('aria-label',config.title || 'Поездки');
      this._updateSpeedLegend();
      this._layer?.clearLayers(); this._load();
    }
    set hass(hass) {
      const first=!this._hass; this._hass=hass;
      if(first) this._load();
    }
    connectedCallback() {
      clearInterval(this._timer); this._timer=setInterval(()=>this._load(),60000);
      document.addEventListener('fullscreenchange',this._onFullscreenChange);
      this._resize=new ResizeObserver(()=>this._map?.invalidateSize());this._resize.observe(this);
      this._load();
    }
    disconnectedCallback(){ clearInterval(this._timer);this._resize?.disconnect();document.removeEventListener('fullscreenchange',this._onFullscreenChange);this.classList.remove('fallback-fullscreen');if(this._nativeFullscreen()&&document.exitFullscreen)document.exitFullscreen().catch(()=>{});this._serial++;this._map?.remove();this._map=null;this._base=null;this._layer=null;this._baseStyle=null;this._fitKey=null; }
    getCardSize(){return 6;}
    _calendar(open){this.shadowRoot.querySelector('.dates').hidden=!open;this.shadowRoot.querySelector('#calendar').setAttribute('aria-expanded',String(open));if(open)this.shadowRoot.querySelector('#start').focus();}
    _highlight(){this.shadowRoot.querySelectorAll('[data-mode]').forEach(b=>b.classList.toggle('active',b.dataset.mode===this._mode));this.shadowRoot.querySelector('#calendar').classList.toggle('active',this._mode==='custom');}
    _updateSpeedLegend(){const limits=speedLimits(this._config);this.shadowRoot.querySelector('.low-range').textContent=`до ${limits.green} км/ч`;this.shadowRoot.querySelector('.medium-range').textContent=`${limits.green}–${limits.red} км/ч`;this.shadowRoot.querySelector('.high-range').textContent=`${limits.red}+ км/ч`;}
    _centerVehicle(){
      const state=this._hass?.states[this._config?.entity];
      const latitude=Number(state?.attributes.latitude),longitude=Number(state?.attributes.longitude);
      if(!this._map)return;
      if(Number.isFinite(latitude)&&Number.isFinite(longitude))this._map.flyTo([latitude,longitude],Math.max(this._map.getZoom(),16),{duration:.45});
      else if(this._layer?.getLayers().length)this._map.fitBounds(this._layer.getBounds(),{padding:[25,25],maxZoom:16});
    }
    async _toggleFullscreen(){
      if(this.classList.contains('fallback-fullscreen')){this._setFallbackFullscreen(false);return;}
      if(this._nativeFullscreen()){await this._exitFullscreen();return;}
      if(this._mapCard.requestFullscreen){
        try{await this._mapCard.requestFullscreen({navigationUI:'hide'});return;}catch{}
      }
      this._setFallbackFullscreen(true);
    }
    _nativeFullscreen(){return this.shadowRoot.fullscreenElement===this._mapCard||document.fullscreenElement===this._mapCard;}
    async _exitFullscreen(){
      if(this._nativeFullscreen()&&document.exitFullscreen)await document.exitFullscreen();
      this._setFallbackFullscreen(false);
      this._fullscreenBtn.focus({preventScroll:true});
    }
    _setFallbackFullscreen(active){this.classList.toggle('fallback-fullscreen',active);this._syncFullscreenButton();requestAnimationFrame(()=>this._map?.invalidateSize());}
    _syncFullscreenButton(){
      const active=this.classList.contains('fallback-fullscreen')||this._nativeFullscreen();
      this._closeMapButton.hidden=!active;
      this._fullscreenBtn.setAttribute('aria-pressed',String(active));
      this._fullscreenBtn.setAttribute('aria-label',active?'Свернуть карту':'Развернуть карту');
      this._fullscreenBtn.title=active?'Свернуть карту':'Развернуть карту';
      this._fullscreenBtn.querySelector('ha-icon').setAttribute('icon',active?'mdi:fullscreen-exit':'mdi:fullscreen');
    }
    _osm(L){return L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,referrerPolicy:'strict-origin-when-cross-origin',attribution:'© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a>'})
      .on('tileerror',()=>{this._baseNeedsRetry=true;this.shadowRoot.querySelector('.map-status').textContent='Подложка карты недоступна.';});}
    async _setBasemap(L,serial){
      const style=this._config.map_style || 'positron';
      if(!Object.hasOwn(STYLES,style))throw new Error('Выберите оформление карты в настройках.');
      if(this._baseStyle===style && !this._baseNeedsRetry)return;
      this._baseNeedsRetry=false;
      const status=this.shadowRoot.querySelector('.map-status');
      try{
        if(style!=='osm')await loadVector(L);
        if(serial!==this._serial || !this.isConnected)return;
        if(this._base)this._map.removeLayer(this._base);this._base=null;status.textContent='';
        this._base=style==='osm'?this._osm(L):L.maplibreGL({style:`https://tiles.openfreemap.org/styles/${style}`,attributionControl:{customAttribution:'<a href="https://openfreemap.org/" target="_blank" rel="noopener">OpenFreeMap</a> · © <a href="https://openmaptiles.org/" target="_blank" rel="noopener">OpenMapTiles</a> · © <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a>'}});
        this._base.addTo(this._map);this._baseStyle=style;
        const activeBase=this._base;
        this._base.getMaplibreMap?.().on('error',()=>{if(this._base===activeBase){this._baseNeedsRetry=true;status.textContent='Не удалось загрузить часть карты. Повторим при обновлении.';}});
      }catch(error){
        if(serial!==this._serial || !this.isConnected)return;
        if(this._base && this._map.hasLayer(this._base))this._map.removeLayer(this._base);
        this._base=this._osm(L).addTo(this._map);this._baseStyle=style;
        status.textContent='OpenFreeMap недоступна. Показана OpenStreetMap.';
      }
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
      if(this._queryKey!==queryKey){this._routeContext=null;this._gpxButton.disabled=true;this._selectedTrip=null;this._overview=null;this._arrowRuns=[];this._arrows?.clearLayers();this._layer?.clearLayers();root.querySelector('.all-trips').hidden=true;root.querySelector('.speed-legend').hidden=true;root.querySelector('.km').textContent='—';this._queryKey=queryKey;}
      error.textContent='';root.querySelector('.summary').setAttribute('aria-busy','true');
      const perfKey=`gwm-trips:${this._config.entity}:${start}:${end}:${serial}`;
      const mark=(suffix)=>{try{performance.mark(`${perfKey}:${suffix}`);}catch{}};
      mark('load-start');
      let timeout;
      try{
        // Start the map and basemap while Home Assistant reads and merges history.
        // Keep errors independent: an unavailable basemap must not delay route data.
        const mapPromise=loadMap().then(async L=>{
          if(serial!==this._serial||!this.isConnected)return null;
          if(!this._map){
            this._map=L.map(root.querySelector('.map'),{scrollWheelZoom:true,dragging:true,touchZoom:true,tap:true}).setView([20,0],2);
            this._map.attributionControl.setPrefix(false);
            this._layer=L.featureGroup().addTo(this._map);
            this._map.on('zoomend moveend',()=>this._drawChevrons());
          }
          await this._setBasemap(L,serial);
          mark('map-ready');
          return L;
        });
        mapPromise.catch(()=>{});
        const includeRecorder=!!this._requestRecorder;this._requestRecorder=false;
        const requestHistory=(skipRecorder)=>this._hass.callWS({type:'gwm_jolion/trips',entity_id:this._config.entity,start,end,...(this._config.odometer_entity?{odometer_entity:this._config.odometer_entity}:{}),...(skipRecorder?{skip_recorder:true}:{})});
        const historyStarted=performance.now();
        const data=await Promise.race([requestHistory(!includeRecorder),new Promise((_,reject)=>{timeout=setTimeout(()=>reject(new Error('Не удалось загрузить историю. Выберите период ещё раз.')),20000);})]);
        mark('history-ready');
        const historyMs=Math.round(performance.now()-historyStarted);
        if(data.server_timings){
          this._lastServerTimings=data.server_timings;
          console.info(`[GWM поездки] Время сервера (${includeRecorder?'Recorder':'локальная история'})`,data.server_timings);
          if(data.server_timings.history_profile)console.info('[GWM поездки] Этапы истории',data.server_timings.history_profile);
        }
        if(serial!==this._serial || !this.isConnected)return;
        error.textContent=data.samples?'':'За этот период нет записей.';
        root.querySelector('.diagnostics').textContent=this._diagnosticText(data,start,end);
        root.querySelector('.diagnostics').hidden=!root.querySelector('.diagnostics').textContent;
        root.querySelector('.km').textContent=data.samples?`${data.method==='odometer'?'':'≈ '}${data.km.toLocaleString('ru-RU')}`:'—';
        root.querySelector('.km').title=`${start} — ${end} · км${data.method==='odometer'?'':' · оценка'}`;
        const L=await mapPromise;if(!L||serial!==this._serial || !this.isConnected)return;
        this._layer.clearLayers();
        // Do not draw a line between the ends of a missing interval. That
        // diagnostic connector looks like a teleport on the overview map.
        // The actual route remains represented by its separate source segments.
        const parkingSpots=Array.isArray(data.parking_spots)?data.parking_spots:[];
        const routeStart=data.segments?.find(segment=>segment.length)?.[0];
        const firstRouteTime=data.segment_timestamps?.find(times=>times.length)?.[0];
        const routeStartParking=Number.isFinite(firstRouteTime)?parkingSpots.find(spot=>Number(spot.start)<=firstRouteTime&&Number(spot.observed_until ?? spot.end ?? -Infinity)>=firstRouteTime&&Math.abs(Number(spot.latitude)-routeStart[0])<0.002&&Math.abs(Number(spot.longitude)-routeStart[1])<0.002):null;
        const routeStartTime=routeStartParking?Number(routeStartParking.start):firstRouteTime;
        const separateStart=!!routeStart&&!routeStartParking;
        if(separateStart){
          const label=document.createElement('div');label.style.whiteSpace='pre-line';
          const showStartDate=Number.isFinite(routeStartTime)&&dayInZone(routeStartTime,this._hass.config.time_zone)!==start;
          label.textContent=`Начало маршрута A${Number.isFinite(routeStartTime)?`\nВремя: ${tripTime(routeStartTime,this._hass.config.time_zone,showStartDate)}`:''}`;
          const iconElement=document.createElement('div');iconElement.className='route-point';iconElement.textContent='A';
          const icon=L.divIcon({className:'',html:iconElement,iconSize:[28,28],iconAnchor:[14,14]});
          L.marker(routeStart,{icon,keyboard:true,title:'Начало маршрута A'}).bindTooltip(label,{direction:'top',offset:[0,-8]}).addTo(this._layer);
        }
        const parkingOccurrencesForPeriod=parkingOccurrences(parkingSpots,start,end,this._hass.config.time_zone,separateStart?1:0),multiDay=start!==end;
        for(const parking of parkingOccurrencesForPeriod){
          const latitude=Number(parking.latitude),longitude=Number(parking.longitude),parkingStart=Number(parking.start),parkingEnd=parking.end===null||parking.end===undefined?NaN:Number(parking.end);
          if(!Number.isFinite(latitude)||!Number.isFinite(longitude)||!Number.isFinite(parkingStart))continue;
          const showDates=multiDay||dayInZone(parkingStart,this._hass.config.time_zone)!==parking.day||(Number.isFinite(parkingEnd)&&dayInZone(parkingStart,this._hass.config.time_zone)!==dayInZone(parkingEnd,this._hass.config.time_zone));
          const label=document.createElement('div');label.style.whiteSpace='pre-line';
          label.textContent=`Стоянка ${parking.label}\nНачало: ${tripTime(parkingStart,this._hass.config.time_zone,showDates)}${parking.show_end?`\nКонец: ${tripTime(parkingEnd,this._hass.config.time_zone,showDates)}`:''}`;
          for(const gap of parking.interruptions || [])label.textContent+=`\nНет данных: ${tripTime(gap[0],this._hass.config.time_zone,true)} — ${tripTime(gap[1],this._hass.config.time_zone,true)}`;
          const iconElement=document.createElement('div');iconElement.className='route-point';iconElement.textContent=parking.label;if(parking.offset_index)iconElement.style.transform=`translateX(${parking.offset_index*20}px)`;
          const icon=L.divIcon({className:'',html:iconElement,iconSize:[28,28],iconAnchor:[14,14]});
          L.marker([latitude,longitude],{icon,keyboard:true,title:`Стоянка ${parking.label}`}).bindTooltip(label,{direction:'top',offset:[0,-8]}).addTo(this._layer);
        }
        if(!this._layer.getLayers().length && start<=today && today<=end){
          const validPosition=value=>value && value.latitude!==null && value.longitude!==null && value.latitude!=='' && value.longitude!=='' && Number.isFinite(Number(value.latitude)) && Number.isFinite(Number(value.longitude)) && Math.abs(Number(value.latitude))<=90 && Math.abs(Number(value.longitude))<=180 && (Number(value.latitude)!==0 || Number(value.longitude)!==0);
          const current=this._hass.states[this._config.entity]?.attributes;
          const position=validPosition(current)?current:validPosition(data.last_position)?data.last_position:null;
          if(position){
            const iconElement=document.createElement('ha-icon');iconElement.setAttribute('icon','mdi:car');iconElement.className='route-point';
            const icon=L.divIcon({className:'',html:iconElement,iconSize:[28,28],iconAnchor:[14,14]});
            L.marker([Number(position.latitude),Number(position.longitude)],{icon,keyboard:true,title:'Последнее известное положение автомобиля'}).bindTooltip('Последнее известное положение автомобиля').addTo(this._layer);
          }
        }
        this._routeContext={L,data,start,end};
        this._gpxButton.disabled=!(data.segments||[]).some(segment=>segment.some(point=>point&&Number.isFinite(point[0])&&Number.isFinite(point[1])&&Math.abs(point[0])<=90&&Math.abs(point[1])<=180));
        this._overviewLayers=this._layer.getLayers().slice();
        this._buildTrips(data);
        this._renderTrips();
        if(this._layer.getLayers().length){this._map.invalidateSize();const key=`${this._config.entity}|${start}|${end}`;if(this._fitKey!==key){this._map.fitBounds(this._layer.getBounds(),{padding:[25,25],maxZoom:16});this._fitKey=key;}}
        else {this._map.setView([20,0],2);this._fitKey=null;}
        mark('render-ready');
        try{performance.measure('gwm-trips:history-request',`${perfKey}:load-start`,`${perfKey}:history-ready`);performance.measure('gwm-trips:map-startup',`${perfKey}:load-start`,`${perfKey}:map-ready`);performance.measure('gwm-trips:render',`${perfKey}:history-ready`,`${perfKey}:render-ready`);performance.measure('gwm-trips:total',`${perfKey}:load-start`,`${perfKey}:render-ready`);}catch{}
        this._lastTimings={history_ms:historyMs,total_ms:Math.round(performance.now()-historyStarted),map_started_with_history:true};
        this._recorderRequests ||= new Set();
        if(!includeRecorder&&data.diagnostics?.recorder_configured&&!this._recorderRequests.has(queryKey)){
          this._recorderRequests.add(queryKey);
          const refreshSerial=serial;
          setTimeout(()=>{
            if(refreshSerial===this._serial&&this.isConnected&&this._queryKey===queryKey){this._requestRecorder=true;this._load();}
            else this._recorderRequests.delete(queryKey);
          },0);
        }else if(includeRecorder){
          this._recorderRequests?.delete(queryKey);
        }
      }catch(err){if(serial===this._serial)error.textContent=err.message || 'Не удалось загрузить историю. Проверьте выбранную сущность.';}
      finally{clearTimeout(timeout);if(serial===this._serial)root.querySelector('.summary').setAttribute('aria-busy','false');}
    }
    _buildTrips(data){
      const stops=(data.parking_spots||[]).filter(p=>Number.isFinite(Number(p.start))).slice().sort((a,b)=>a.start-b.start);
      const groups=new Map();
      // A trip is the interval between the end of one stop and the start of the
      // next. The stop itself is deliberately excluded: otherwise the last GPS
      // wobble at B becomes a new blue/purple leg before the B marker.
      const windows=Array.from({length:stops.length+1},(_,index)=>({
        index,
        from: index?stops[index-1]:null,
        to: stops[index]||null,
        start: index ? Number(stops[index-1].end ?? stops[index-1].observed_until ?? Infinity) : -Infinity,
        end: index<stops.length ? Number(stops[index].start) : Infinity,
      })).filter(w=>w.end>w.start);
      for(const [s,segment] of (data.segments||[]).entries()){
        let run=null,lastEdge=-1;
        const times=data.segment_timestamps?.[s]||[];
        const nextKnown=[];let known=null;
        for(let i=segment.length-1;i>=0;i--){if(Number.isFinite(times[i]))known=times[i];nextKnown[i]=known;}
        let previousKnown=null;
        for(let i=1;i<segment.length;i++){
          const t=times[i-1];
          if(Number.isFinite(t))previousKnown=t;
          const stamp=previousKnown??nextKnown[i];
          const nextStamp=Number.isFinite(times[i])?times[i]:stamp;
          const window=windows.find(w=>Number.isFinite(stamp)&&Number.isFinite(nextStamp)
            &&nextStamp>w.start&&stamp<w.end);
          const parked=stops.some(stop=>Number(stop.start)<=stamp
            &&Number(stop.end??stop.observed_until??Infinity)>=nextStamp);
          if(parked)continue;
          // Missing time cannot safely be assigned around a stop. Preserve it
          // as an unclassified leg rather than painting it as a trip.
          const fallback=!window;
          const {index,from,to}=window||{index:stops.length+1,from:null,to:null};
          const key=fallback?`unclassified-${s}`:String(index),unclassified=fallback;
          // Each source edge has one owner and retains its original geometry.
          // Separate source segments remain separate runs even in the same trip.
          const a=segment[i-1],b=segment[i];
          if(!groups.has(key))groups.set(key,{key,index,from,to,unclassified,runs:[]});
          const group=groups.get(key);
          if(!run||run.key!==key||lastEdge!==i-1){run={key,points:[a],speeds:[],kinds:[]};group.runs.push(run);}
          run.points.push(b);run.speeds.push(data.segment_speeds_kmh?.[s]?.[i-1]);run.kinds.push(data.segment_kinds?.[s]?.[i-1]);lastEdge=i;
        }
      }
      this._trips=[...groups.values()];
      if(!this._trips.some(t=>t.key===this._selectedTrip))this._selectedTrip=null;
    }
    _selectTrip(key){
      if(!this._map||!this._routeContext)return;
      if(key!=null&&this._selectedTrip==null)this._overview={center:this._map.getCenter(),zoom:this._map.getZoom()};
      this._selectedTrip=key;this._renderTrips();
      if(key==null){if(this._overview)this._map.setView(this._overview.center,this._overview.zoom,{animate:false});this._overview=null;}
      else if(this._routeLayer.getLayers().length)this._map.fitBounds(this._routeLayer.getBounds(),{padding:[35,55],maxZoom:17,animate:false});
      this._drawChevrons();
      if(key!=null)this.shadowRoot.querySelector('.all-trips').focus({preventScroll:true});
    }
    _renderTrips(){
      const {L}=this._routeContext,focused=this._selectedTrip!=null,limits=speedLimits(this._config);
      if(this._routeLayer)this._layer.removeLayer(this._routeLayer);
      if(this._arrows)this._map.removeLayer(this._arrows);
      for(const layer of this._overviewLayers||[]){if(focused)this._layer.removeLayer(layer);else if(!this._layer.hasLayer(layer))this._layer.addLayer(layer);}
      this._routeLayer=L.featureGroup().addTo(this._layer);this._arrows=L.layerGroup().addTo(this._map);this._arrowRuns=[];
      const trips=this._trips.filter(t=>!focused||t.key===this._selectedTrip);
      for(const trip of trips)for(const run of trip.runs){
        // Round caps turn a run of identical parked fixes into a stray colored
        // dot. Parking markers already represent these stationary observations.
        if(!run.points.some(p=>p[0]!==run.points[0][0]||p[1]!==run.points[0][1]))continue;
        const common={lineCap:'round',lineJoin:'round',smoothFactor:.6,bubblingMouseEvents:false};
        L.polyline(run.points,{...common,color:'#fff',weight:9,opacity:.85,interactive:false}).addTo(this._routeLayer);
        const title=trip.unclassified?'Участок с неуточнёнными границами стоянки':`Участок ${trip.index+1}`;
        if(!focused)L.polyline(run.points,{...common,color:TRIP_COLORS[trip.index%TRIP_COLORS.length],weight:6,opacity:.95,interactive:false}).addTo(this._routeLayer);
        else {
          let batch=[],lastColor;
          const flush=()=>{if(batch.length>1)L.polyline(batch,{...common,color:lastColor,weight:6,opacity:.95,interactive:false}).addTo(this._routeLayer);};
          for(let i=1;i<run.points.length;i++){
            const speed=run.speeds[i-1],valid=speed!=null&&Number.isFinite(Number(speed))&&Number(speed)>0&&run.kinds[i-1]!=='unknown'&&run.kinds[i-1]!=='stationary';
            const color=!valid?'#88949f':speed<limits.green?SPEED_COLORS.low:speed<limits.red?SPEED_COLORS.medium:SPEED_COLORS.high;
            if(color!==lastColor){flush();batch=[run.points[i-1]];lastColor=color;}batch.push(run.points[i]);
          }flush();
        }
        const hit=L.polyline(run.points,{...common,color:'#000',weight:20,opacity:0,className:'route-hit'}).bindTooltip(focused?`${title} · цвет показывает скорость`:`${title} · нажмите для просмотра скорости`).addTo(this._routeLayer);
        hit.on('click',()=>{if(!focused)this._selectTrip(trip.key);});
        if(focused)hit.on('mousemove',event=>{
          const cursor=this._map.latLngToContainerPoint(event.latlng);let nearest=Infinity,edge=0;
          for(let i=1;i<run.points.length;i++){
            const a=this._map.latLngToContainerPoint(run.points[i-1]),b=this._map.latLngToContainerPoint(run.points[i]);
            const dx=b.x-a.x,dy=b.y-a.y,length=dx*dx+dy*dy;
            const fraction=length?Math.max(0,Math.min(1,((cursor.x-a.x)*dx+(cursor.y-a.y)*dy)/length)):0;
            const distance=(cursor.x-a.x-fraction*dx)**2+(cursor.y-a.y-fraction*dy)**2;
            if(distance<nearest){nearest=distance;edge=i-1;}
          }
          const speed=run.speeds[edge],known=speed!=null&&Number.isFinite(Number(speed))&&Number(speed)>=0&&run.kinds[edge]!=='unknown';
          hit.setTooltipContent(known?`Средняя скорость: ${Math.round(Number(speed))} км/ч`:'Скорость неизвестна');
          hit.openTooltip(event.latlng);
        });
        const path=hit.getElement?.();if(path&&!focused){path.setAttribute('tabindex','0');path.setAttribute('role','button');path.setAttribute('aria-label',`${title}: показать скорость`);path.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();this._selectTrip(trip.key);}});}
        this._arrowRuns.push(run.points);
      }
      if(focused&&trips.length){
        const trip=trips[0],runs=trip.runs;
        const endpoints=[[trip.from,runs[0].points[0],'Начальная стоянка'],[trip.to,runs.at(-1).points.at(-1),'Конечная стоянка']];
        for(const [stop,fix,text] of endpoints){
          const point=stop?[Number(stop.latitude),Number(stop.longitude)]:fix;
          if(stop&&this._map.distance(point,fix)>3)L.polyline([point,fix],{color:'#88949f',weight:2,dashArray:'5 7',interactive:true}).bindTooltip('Связь со стоянкой: точная траектория не записана').addTo(this._routeLayer);
          L.circleMarker(point,{radius:6,color:'#fff',weight:3,fillColor:'#334155',fillOpacity:1}).bindTooltip(stop?text:'Граница доступной GPS-записи').addTo(this._routeLayer);
        }
        for(let i=1;i<runs.length;i++){
          const a=runs[i-1].points.at(-1),b=runs[i].points[0];
          if(this._map.distance(a,b)>3)L.polyline([a,b],{color:'#88949f',weight:2,dashArray:'5 7'}).bindTooltip('Разрыв GPS-записи: точная траектория неизвестна').addTo(this._routeLayer);
        }
      }
      this.shadowRoot.querySelector('.all-trips').hidden=!focused;
      this.shadowRoot.querySelector('.trip-caption').hidden=true;
      this.shadowRoot.querySelector('.speed-legend').hidden=!focused;
      this._drawChevrons();
    }
    _drawChevrons(){
      if(!this._map||!this._arrows||!this._routeContext)return;
      this._arrows.clearLayers();const {L}=this._routeContext,size=this._map.getSize(),paths=[];
      for(const run of this._arrowRuns||[]){let remaining=24;
        for(let i=1;i<run.length;i++){
          const a=this._map.latLngToContainerPoint(run[i-1]),b=this._map.latLngToContainerPoint(run[i]);
          const dx=b.x-a.x,dy=b.y-a.y,length=Math.hypot(dx,dy);if(!length)continue;
          const ux=dx/length,uy=dy/length;
          // Pixel spacing is stable at every zoom; offscreen arrows use no layers.
          let low=0,high=length;
          for(const [origin,unit,max] of [[a.x,ux,size.x],[a.y,uy,size.y]]){
            if(Math.abs(unit)<1e-9){if(origin<0||origin>max)high=-1;}
            else {const enter=(0-origin)/unit,exit=(max-origin)/unit;low=Math.max(low,Math.min(enter,exit));high=Math.min(high,Math.max(enter,exit));}
          }
          const first=remaining+Math.max(0,Math.ceil((low-remaining)/38))*38;
          for(let d=first;d<=high;d+=38){const x=a.x+ux*d,y=a.y+uy*d;
            paths.push([[x-ux*4-uy*3,y-uy*4+ux*3],[x,y],[x-ux*4+uy*3,y-uy*4-ux*3]].map(p=>this._map.containerPointToLatLng(p)));
            if(paths.length>=1600)break;
          }
          remaining=((remaining-length)%38+38)%38||38;if(paths.length>=1600)break;
        }if(paths.length>=1600)break;
      }
      if(paths.length)L.polyline(paths,{color:'#fff',weight:1.8,opacity:.95,interactive:false,lineCap:'round',lineJoin:'round',smoothFactor:0}).addTo(this._arrows);
    }
    _diagnosticText(data,start,end){
      const info=data.diagnostics||{},counts=info.source_counts||data.source_counts||{},app=Number(counts.app)||0,cloud=Number(counts.cloud)||0;
      const hasRoute=Array.isArray(data.segments)&&data.segments.some(segment=>segment.length>0);
      const messages=[];
      const retention=Number(info.retention_days||data.retention_days);
      const today=dateInZone(this._hass.config.time_zone);
      const expired=Number.isFinite(retention)&&shift(today,-retention)>=end;
      if(expired)messages.push(`Локальная история за этот период уже удалена (срок хранения — ${retention} дней).`);
      if(info.recorder_error)messages.push('Архив Home Assistant Recorder сейчас недоступен.');
      else if(info.recorder_skipped){}
      else if(info.recorder_available===false)messages.push('Архив Recorder недоступен или не включён.');
      if(info.locator_enabled===false)messages.push('Сбор Jolion Locator выключен.');
      else if(info.locator_enabled===true&&app===0)messages.push('За этот период нет точек от Jolion Locator.');
      if(!hasRoute){
        if(cloud===0&&app===0)messages.push('Нет GPS-координат за выбранный период.');
        else if(Number(data.samples)>0)messages.push('Есть записи, но GPS-координаты отсутствуют; проверьте доступность передачи GPS автомобиля.');
      }else if((data.gaps||[]).length)messages.push('Маршрут неполный: есть интервалы без GPS-данных (пунктир на карте).');
      return messages.join(' ');
    }
  }
  class TripsEditor extends HTMLElement{
    setConfig(config){
      this._config=config;const limits=speedLimits(config);
      for(const [key,field] of Object.entries(this._fields || {})){
        if(this._editingSpeed&&['speed_green_max','speed_red_min'].includes(key))continue;
        field.value=key==='show_download_gpx'?config[key]===true:key==='show_download_points'?config[key]!==false:key==='speed_green_max'?limits.green:key==='speed_red_min'?limits.red:config[key] || (key==='map_style'?'positron':'');
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
      const label=document.createElement('label');label.textContent='Оформление карты';
      const field=document.createElement('ha-selector');field.hass=this._hass;field.selector={select:{mode:'dropdown',options:Object.entries(STYLES).map(([value,label])=>({value,label}))}};field.value=this._config.map_style || 'positron';this._fields.map_style=field;
      field.addEventListener('value-changed',e=>{this._config={...this._config,map_style:e.detail.value};this.dispatchEvent(new CustomEvent('config-changed',{detail:{config:this._config},bubbles:true,composed:true}));});this.append(label,field);
      const section=document.createElement('div');section.textContent='Диапазоны цветов скорости';section.style.cssText='font-weight:600;margin:4px 0 12px';this.append(section);
      const downloadLabel=document.createElement('label');downloadLabel.textContent='Показывать кнопку «Скачать точки»';
      const downloadField=document.createElement('ha-selector');downloadField.hass=this._hass;downloadField.selector={boolean:{}};downloadField.value=this._config.show_download_points!==false;this._fields.show_download_points=downloadField;
      downloadField.addEventListener('value-changed',e=>{this._config={...this._config,show_download_points:!!e.detail.value};this.dispatchEvent(new CustomEvent('config-changed',{detail:{config:this._config},bubbles:true,composed:true}));});this.append(downloadLabel,downloadField);
      const gpxLabel=document.createElement('label');gpxLabel.textContent='Показывать кнопку «Скачать GPX»';
      const gpxField=document.createElement('ha-selector');gpxField.hass=this._hass;gpxField.selector={boolean:{}};gpxField.value=this._config.show_download_gpx===true;this._fields.show_download_gpx=gpxField;
      gpxField.addEventListener('value-changed',e=>{this._config={...this._config,show_download_gpx:!!e.detail.value};this.dispatchEvent(new CustomEvent('config-changed',{detail:{config:this._config},bubbles:true,composed:true}));});this.append(gpxLabel,gpxField);
      const limits=speedLimits(this._config);
      for(const [key,title] of [['speed_green_max','Зелёный: до, км/ч'],['speed_red_min','Красный: от, км/ч']]){
        const speedLabel=document.createElement('label');speedLabel.textContent=title;
        const speedField=document.createElement('ha-selector');speedField.hass=this._hass;speedField.selector={number:{min:1,max:300,step:1,mode:'box',unit_of_measurement:'км/ч'}};speedField.value=key==='speed_green_max'?limits.green:limits.red;speedField.style.display='block';speedField.style.marginBottom='16px';this._fields[key]=speedField;
        speedField.addEventListener('focusin',()=>{this._editingSpeed=true;});
        speedField.addEventListener('value-changed',event=>{
          const value=event.detail.value;
          this._config={...this._config,[key]:value};
          this.dispatchEvent(new CustomEvent('config-changed',{detail:{config:this._config},bubbles:true,composed:true}));
        });
        speedField.addEventListener('focusout',()=>{
          setTimeout(()=>{
            if(this._fields.speed_green_max.matches(':focus-within')||this._fields.speed_red_min.matches(':focus-within'))return;
            this._editingSpeed=false;
            const next=speedLimits(this._config);
            this._config={...this._config,speed_green_max:next.green,speed_red_min:next.red};
            this._fields.speed_green_max.value=next.green;this._fields.speed_red_min.value=next.red;
            this.dispatchEvent(new CustomEvent('config-changed',{detail:{config:this._config},bubbles:true,composed:true}));
          },0);
        });
        this.append(speedLabel,speedField);
      }
    }
  }
  if(!customElements.get('gwm-jolion-trips-card'))customElements.define('gwm-jolion-trips-card',TripsCard);
  if(!customElements.get('gwm-jolion-trips-card-editor'))customElements.define('gwm-jolion-trips-card-editor',TripsEditor);
  window.customCards=window.customCards || [];window.customCards.push({type:'gwm-jolion-trips-card',name:'GWM Jolion — Поездки',description:'Карта маршрута и пробег за день или период',preview:true});
})();
