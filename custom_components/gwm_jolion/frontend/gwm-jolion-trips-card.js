/* GWM Jolion Trips Card v0.1.0-beta.18 */
(() => {
  let leaflet;
  const STYLES = {positron:'Светлая · OpenFreeMap',dark:'Тёмная · OpenFreeMap',liberty:'Стандартная · OpenFreeMap',osm:'OpenStreetMap'};
  const SPEED_COLORS = {low:'#2e7d32',medium:'#f9a825',high:'#c62828'};
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
  function tripTime(value, zone){return new Intl.DateTimeFormat('ru-RU',{timeZone:zone,day:'2-digit',month:'2-digit',year:'numeric',hour:'2-digit',minute:'2-digit'}).format(new Date(value*1000));}
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
        .speed-legend{display:flex;justify-content:center;gap:12px;flex-wrap:wrap;margin:0 0 10px;color:var(--secondary-text-color);font-size:11px}.speed-legend[hidden]{display:none}.speed-legend span{display:flex;align-items:center;gap:4px}.speed-legend i{width:10px;height:4px;border-radius:2px;background:#888}.speed-legend b{font-weight:400}.speed-legend .low{background:#2e7d32}.speed-legend .medium{background:#f9a825}.speed-legend .high{background:#c62828}.speed-legend .parking{width:9px;height:9px;border-radius:50%;background:#fff;border:2px solid #455a64}
        .error,.map-status{color:var(--secondary-text-color);font-size:12px;text-align:center}.error:empty,.map-status:empty{display:none}.error:not(:empty),.map-status:not(:empty){margin-top:8px}.map-wrap{position:relative;height:300px;background:#e9edef}.map{height:100%;background:#e9edef;z-index:0}
        .map-actions{position:absolute;top:8px;right:8px;z-index:1000;display:flex;gap:6px}.map-actions button{display:flex;align-items:center;justify-content:center;width:34px;height:34px;padding:0;background:var(--card-background-color,#fff);box-shadow:0 1px 5px rgba(0,0,0,.28)}.map-actions ha-icon{--mdc-icon-size:19px}
        :host(.fallback-fullscreen){position:fixed;inset:0;z-index:1000;display:block;background:var(--card-background-color,#fff)}:host(.fallback-fullscreen) ha-card,ha-card:fullscreen{width:100%;height:100%;min-height:100%;display:flex;flex-direction:column;border-radius:0;background:var(--card-background-color,#fff)}:host(.fallback-fullscreen) .map-wrap,ha-card:fullscreen .map-wrap{flex:1;height:auto;min-height:0}:host(.fallback-fullscreen) .content,ha-card:fullscreen .content{display:none}
        .leaflet-container{font-family:inherit}.leaflet-control-attribution{font-size:10px}
        @media(max-width:350px){button{padding:7px 8px}.content{padding:10px}.map-wrap{height:260px}}
      </style><ha-card><div class="map-wrap"><div class="map" aria-label="Карта маршрута"></div><div class="map-actions"><button id="centerBtn" type="button" title="Показать автомобиль в центре карты" aria-label="Показать автомобиль в центре карты"><ha-icon icon="mdi:crosshairs-gps"></ha-icon></button><button id="fullscreenBtn" type="button" title="Развернуть карту" aria-label="Развернуть карту" aria-pressed="false"><ha-icon icon="mdi:fullscreen"></ha-icon></button></div></div><div class="content">
      <div class="speed-legend" aria-label="Цвета средней скорости и стоянки" hidden><span><i class="low"></i><b class="low-range">до 80 км/ч</b></span><span><i class="medium"></i><b class="medium-range">80–110 км/ч</b></span><span><i class="high"></i><b class="high-range">110+ км/ч</b></span><span><i class="parking"></i>Стоянка</span></div>
      <div class="summary"><ha-icon icon="mdi:counter" aria-hidden="true"></ha-icon><span class="km" aria-label="Пробег за выбранный период">—</span></div>
      <div class="shortcuts"><button data-mode="today">Сегодня</button><button data-mode="yesterday">Вчера</button><button data-mode="week">Неделя</button><button id="calendar" title="Выбрать период" aria-label="Выбрать период" aria-expanded="false" aria-controls="period"><ha-icon icon="mdi:calendar-range"></ha-icon></button></div>
      <div class="dates" id="period" hidden><label>С<input type="date" id="start"></label><label>По<input type="date" id="end"></label><button id="show">Выбрать</button></div>
      <div class="error" role="status"></div><div class="map-status" role="status"></div></div></ha-card>`;
      this._mapCard=this.shadowRoot.querySelector('ha-card');
      this._fullscreenBtn=this.shadowRoot.querySelector('#fullscreenBtn');
      this.shadowRoot.querySelector('#centerBtn').onclick=()=>this._centerVehicle();
      this._fullscreenBtn.onclick=()=>this._toggleFullscreen();
      this._onFullscreenChange=()=>{this._syncFullscreenButton();requestAnimationFrame(()=>this._map?.invalidateSize());};
      this.shadowRoot.querySelectorAll('[data-mode]').forEach(button => button.onclick=()=>{this._mode=button.dataset.mode;this._calendar(false);this._load();});
      this.shadowRoot.querySelector('#show').onclick=()=>{const start=this.shadowRoot.querySelector('#start').value,end=this.shadowRoot.querySelector('#end').value;if(!start || !end || start>end){this.shadowRoot.querySelector('.error').textContent='Проверьте даты.';return;}this._mode='custom';this._range=[start,end];this._calendar(false);this._load();};
      this.shadowRoot.querySelector('#calendar').onclick=()=>this._calendar(this.shadowRoot.querySelector('.dates').hidden);
    }
    setConfig(config) {
      this._config={...config}; this._serial++;this._fitKey=null;
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
    disconnectedCallback(){ clearInterval(this._timer);this._resize?.disconnect();document.removeEventListener('fullscreenchange',this._onFullscreenChange);this.classList.remove('fallback-fullscreen');if(document.fullscreenElement===this._mapCard&&document.exitFullscreen)document.exitFullscreen().catch(()=>{});this._serial++;this._map?.remove();this._map=null;this._base=null;this._layer=null;this._baseStyle=null;this._fitKey=null; }
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
      if(document.fullscreenElement===this._mapCard){if(document.exitFullscreen)await document.exitFullscreen();return;}
      if(this._mapCard.requestFullscreen){
        try{await this._mapCard.requestFullscreen({navigationUI:'hide'});return;}catch{}
      }
      this._setFallbackFullscreen(true);
    }
    _setFallbackFullscreen(active){this.classList.toggle('fallback-fullscreen',active);this._syncFullscreenButton();requestAnimationFrame(()=>this._map?.invalidateSize());}
    _syncFullscreenButton(){
      const active=this.classList.contains('fallback-fullscreen')||document.fullscreenElement===this._mapCard;
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
      if(this._queryKey!==queryKey){this._layer?.clearLayers();root.querySelector('.km').textContent='—';this._queryKey=queryKey;}
      error.textContent='';root.querySelector('.summary').setAttribute('aria-busy','true');
      let timeout;
      try{
        const data=await Promise.race([this._hass.callWS({type:'gwm_jolion/trips',entity_id:this._config.entity,start,end,...(this._config.odometer_entity?{odometer_entity:this._config.odometer_entity}:{})}),new Promise((_,reject)=>{timeout=setTimeout(()=>reject(new Error('Не удалось загрузить историю. Выберите период ещё раз.')),20000);})]);
        if(serial!==this._serial || !this.isConnected)return;
        error.textContent=data.samples?'':'За этот период нет записей.';
        root.querySelector('.km').textContent=data.samples?`${data.method==='odometer'?'':'≈ '}${data.km.toLocaleString('ru-RU')}`:'—';
        root.querySelector('.km').title=`${start} — ${end} · км${data.method==='odometer'?'':' · оценка'}`;
        const L=await loadMap();if(serial!==this._serial || !this.isConnected)return;
        if(!this._map){
          this._map=L.map(root.querySelector('.map'),{scrollWheelZoom:true,dragging:true,touchZoom:true,tap:true}).setView([20,0],2);
          this._map.attributionControl.setPrefix(false);
          this._layer=L.featureGroup().addTo(this._map);
        }
        await this._setBasemap(L,serial);if(serial!==this._serial || !this.isConnected)return;
        this._layer.clearLayers();
        for(const gap of data.gaps || [])L.polyline(gap,{color:'#88949f',weight:2,dashArray:'5 7',opacity:.7}).bindTooltip('Нет GPS-данных: связь между точками, не записанный маршрут').addTo(this._layer);
        const speedSegments=Array.isArray(data.segment_speeds_kmh)?data.segment_speeds_kmh:[];
        const speedKinds=Array.isArray(data.segment_kinds)?data.segment_kinds:[];
        const parkingSpots=Array.isArray(data.parking_spots)?data.parking_spots:[];
        const hasSpeeds=speedSegments.length===data.segments.length;
        const hasSpeedData=hasSpeeds&&speedSegments.some(segment=>Array.isArray(segment)&&segment.some(speed=>Number(speed)>0));
        const limits=speedLimits(this._config);
        root.querySelector('.speed-legend').hidden=!hasSpeedData&&!parkingSpots.length;
        for(const [segmentIndex,segment] of data.segments.entries()){
          if(!hasSpeeds){if(segment.length>1)L.polyline(segment,{color:'#009fce',weight:4,opacity:.85}).addTo(this._layer);else if(segment.length)L.circleMarker(segment[0],{radius:4,color:'#009fce'}).addTo(this._layer);continue;}
          const speeds=speedSegments[segmentIndex]||[],kinds=speedKinds[segmentIndex]||[];
          for(let index=1;index<segment.length;index++){
            const rawSpeed=speeds[index-1],speed=Number(rawSpeed);
            if(kinds[index-1]==='stationary'||kinds[index-1]==='unknown'||rawSpeed===null||rawSpeed===undefined||!Number.isFinite(speed)||speed<=0)continue;
            const color=speed<limits.green?SPEED_COLORS.low:speed<limits.red?SPEED_COLORS.medium:SPEED_COLORS.high;
            L.polyline([segment[index-1],segment[index]],{color,weight:4,opacity:.9}).bindTooltip(`Средняя скорость: ${Math.round(speed)} км/ч`).addTo(this._layer);
          }
          if(segment.length===1)L.circleMarker(segment[0],{radius:4,color:'#009fce'}).addTo(this._layer);
        }
        for(const parking of parkingSpots){
          const latitude=Number(parking.latitude),longitude=Number(parking.longitude),start=Number(parking.start),end=parking.end===null||parking.end===undefined?NaN:Number(parking.end);
          if(!Number.isFinite(latitude)||!Number.isFinite(longitude)||!Number.isFinite(start))continue;
          const label=document.createElement('div');label.style.whiteSpace='pre-line';
          label.textContent=`Стоянка\nНачало: ${tripTime(start,this._hass.config.time_zone)}${Number.isFinite(end)?`\nКонец: ${tripTime(end,this._hass.config.time_zone)}`:''}`;
          L.circleMarker([latitude,longitude],{radius:7,color:'#455a64',fillColor:'#fff',fillOpacity:1,weight:3}).bindTooltip(label,{direction:'top',offset:[0,-6]}).addTo(this._layer);
        }
        const points=data.segments.flat();
        if(points.length){L.circleMarker(points[0],{radius:7,color:'#263238',fillColor:'#fff',fillOpacity:1,weight:3}).bindTooltip('Начало записанного маршрута').addTo(this._layer);L.circleMarker(points.at(-1),{radius:7,color:'#263238',fillColor:'#263238',fillOpacity:1}).bindTooltip('Последняя точка').addTo(this._layer);this._map.invalidateSize();const key=`${this._config.entity}|${start}|${end}`;if(this._fitKey!==key){this._map.fitBounds(this._layer.getBounds(),{padding:[25,25],maxZoom:16});this._fitKey=key;}}
        else {this._map.setView([20,0],2);this._fitKey=null;}
      }catch(err){if(serial===this._serial)error.textContent=err.message || 'Не удалось загрузить историю. Проверьте выбранную сущность.';}
      finally{clearTimeout(timeout);if(serial===this._serial)root.querySelector('.summary').setAttribute('aria-busy','false');}
    }
  }
  class TripsEditor extends HTMLElement{
    setConfig(config){
      this._config=config;const limits=speedLimits(config);
      for(const [key,field] of Object.entries(this._fields || {})){
        field.value=key==='speed_green_max'?limits.green:key==='speed_red_min'?limits.red:config[key] || (key==='map_style'?'positron':'');
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
      const limits=speedLimits(this._config);
      for(const [key,title] of [['speed_green_max','Зелёный: до, км/ч'],['speed_red_min','Красный: от, км/ч']]){
        const speedLabel=document.createElement('label');speedLabel.textContent=title;
        const speedField=document.createElement('ha-selector');speedField.hass=this._hass;speedField.selector={number:{min:1,max:300,step:1,mode:'box',unit_of_measurement:'км/ч'}};speedField.value=limits[key];speedField.style.display='block';speedField.style.marginBottom='16px';this._fields[key]=speedField;
        speedField.addEventListener('value-changed',event=>{const next=speedLimits({...this._config,[key]:event.detail.value});this._config={...this._config,speed_green_max:next.green,speed_red_min:next.red};this._fields.speed_green_max.value=next.green;this._fields.speed_red_min.value=next.red;this.dispatchEvent(new CustomEvent('config-changed',{detail:{config:this._config},bubbles:true,composed:true}));});this.append(speedLabel,speedField);
      }
    }
  }
  if(!customElements.get('gwm-jolion-trips-card'))customElements.define('gwm-jolion-trips-card',TripsCard);
  if(!customElements.get('gwm-jolion-trips-card-editor'))customElements.define('gwm-jolion-trips-card-editor',TripsEditor);
  window.customCards=window.customCards || [];window.customCards.push({type:'gwm-jolion-trips-card',name:'GWM Jolion — Поездки',description:'Карта маршрута и пробег за день или период',preview:true});
})();
