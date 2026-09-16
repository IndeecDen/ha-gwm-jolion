/* GWM Jolion Trips Card v0.1.0-beta.12.1 */
(() => {
  let leaflet;
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
  class TripsCard extends HTMLElement {
    static getConfigElement() { return document.createElement('gwm-jolion-trips-card-editor'); }
    static getStubConfig(hass) {
      return {entity: Object.keys(hass.states).find(id => id.startsWith('device_tracker.') && id.endsWith('_location')) || '', title:'Поездки'};
    }
    constructor() {
      super(); this.attachShadow({mode:'open'}); this._mode='today'; this._serial=0;
      this.shadowRoot.innerHTML = `<link rel="stylesheet" href="/gwm-jolion/leaflet/leaflet.css">
      <style>
        :host{display:block}ha-card{overflow:hidden}.content{padding:10px 14px 12px}
        .shortcuts,.dates,.summary{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
        button,input{font:inherit;font-size:13px;color:var(--primary-text-color);border:0;border-radius:10px;background:var(--secondary-background-color,#eee);padding:7px 11px;box-sizing:border-box}
        button{cursor:pointer}button.active{background:var(--primary-color,#03a9f4);color:white;border-color:transparent}
        button:focus-visible,input:focus-visible{outline:2px solid var(--primary-color,#03a9f4);outline-offset:2px}
        .dates{margin:10px 0 0}.dates[hidden]{display:none}label{display:flex;flex:1;min-width:110px;flex-direction:column;gap:5px;color:var(--secondary-text-color);font-size:12px}input{width:100%;color-scheme:light dark}
        .summary{justify-content:center;margin:0 0 10px;gap:8px}.km{font-size:26px;font-weight:600;font-variant-numeric:tabular-nums}.summary ha-icon{color:var(--secondary-text-color);--mdc-icon-size:22px}.shortcuts{justify-content:center;flex-wrap:nowrap;gap:6px}#calendar{display:flex;align-items:center;justify-content:center;width:34px;height:32px;padding:0}#calendar ha-icon{--mdc-icon-size:19px}
        .error,.map-status{color:var(--secondary-text-color);font-size:12px;text-align:center}.error:empty,.map-status:empty{display:none}.error:not(:empty),.map-status:not(:empty){margin-top:8px}.map{height:300px;background:#e9edef;z-index:0}
        .leaflet-container{font-family:inherit}.leaflet-control-attribution{font-size:10px}
        @media(max-width:350px){button{padding:7px 8px}.content{padding:10px}.map{height:260px}}
      </style><ha-card><div class="map" aria-label="Карта маршрута"></div><div class="content">
      <div class="summary"><ha-icon icon="mdi:counter" aria-hidden="true"></ha-icon><span class="km" aria-label="Пробег за выбранный период">—</span></div>
      <div class="shortcuts"><button data-mode="today">Сегодня</button><button data-mode="yesterday">Вчера</button><button data-mode="week">Неделя</button><button id="calendar" title="Выбрать период" aria-label="Выбрать период" aria-expanded="false" aria-controls="period"><ha-icon icon="mdi:calendar-range"></ha-icon></button></div>
      <div class="dates" id="period" hidden><label>С<input type="date" id="start"></label><label>По<input type="date" id="end"></label><button id="show">Выбрать</button></div>
      <div class="error" role="status"></div><div class="map-status" role="status"></div></div></ha-card>`;
      this.shadowRoot.querySelectorAll('[data-mode]').forEach(button => button.onclick=()=>{this._mode=button.dataset.mode;this._calendar(false);this._load();});
      this.shadowRoot.querySelector('#show').onclick=()=>{const start=this.shadowRoot.querySelector('#start').value,end=this.shadowRoot.querySelector('#end').value;if(!start || !end || start>end){this.shadowRoot.querySelector('.error').textContent='Проверьте даты.';return;}this._mode='custom';this._range=[start,end];this._calendar(false);this._load();};
      this.shadowRoot.querySelector('#calendar').onclick=()=>this._calendar(this.shadowRoot.querySelector('.dates').hidden);
    }
    setConfig(config) {
      this._config={...config}; this._serial++;this._fitKey=null;
      this.setAttribute('aria-label',config.title || 'Поездки');
      this._layer?.clearLayers(); this._load();
    }
    set hass(hass) {
      const first=!this._hass; this._hass=hass;
      if(first) this._load();
    }
    connectedCallback() {
      clearInterval(this._timer); this._timer=setInterval(()=>this._load(),60000);
      this._resize=new ResizeObserver(()=>this._map?.invalidateSize());this._resize.observe(this);
      this._load();
    }
    disconnectedCallback(){ clearInterval(this._timer);this._resize?.disconnect();this._serial++; }
    getCardSize(){return 6;}
    _calendar(open){this.shadowRoot.querySelector('.dates').hidden=!open;this.shadowRoot.querySelector('#calendar').setAttribute('aria-expanded',String(open));if(open)this.shadowRoot.querySelector('#start').focus();}
    _highlight(){this.shadowRoot.querySelectorAll('[data-mode]').forEach(b=>b.classList.toggle('active',b.dataset.mode===this._mode));this.shadowRoot.querySelector('#calendar').classList.toggle('active',this._mode==='custom');}
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
          this._map=L.map(root.querySelector('.map'),{scrollWheelZoom:false}).setView([20,0],2);
          L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,referrerPolicy:'strict-origin-when-cross-origin',attribution:'© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a>'})
            .on('tileerror',()=>{root.querySelector('.map-status').textContent='Подложка карты недоступна. Проверьте подключение к интернету.';}).addTo(this._map);
          this._layer=L.featureGroup().addTo(this._map);
        }
        this._layer.clearLayers();
        for(const segment of data.segments){if(segment.length>1)L.polyline(segment,{color:'#009fce',weight:4,opacity:.85}).addTo(this._layer);else if(segment.length)L.circleMarker(segment[0],{radius:4,color:'#009fce'}).addTo(this._layer);}
        const points=data.segments.flat();
        if(points.length){L.circleMarker(points[0],{radius:7,color:'#198754',fillOpacity:1}).bindTooltip('Начало записанного маршрута').addTo(this._layer);L.circleMarker(points.at(-1),{radius:7,color:'#d35454',fillOpacity:1}).bindTooltip('Последняя точка').addTo(this._layer);this._map.invalidateSize();const key=`${this._config.entity}|${start}|${end}`;if(this._fitKey!==key){this._map.fitBounds(this._layer.getBounds(),{padding:[25,25],maxZoom:16});this._fitKey=key;}}
        else {this._map.setView([20,0],2);this._fitKey=null;}
      }catch(err){if(serial===this._serial)error.textContent=err.message || 'Не удалось загрузить историю. Проверьте выбранную сущность.';}
      finally{clearTimeout(timeout);if(serial===this._serial)root.querySelector('.summary').setAttribute('aria-busy','false');}
    }
  }
  class TripsEditor extends HTMLElement{
    setConfig(config){this._config=config;for(const [key,field] of Object.entries(this._fields || {}))field.value=config[key] || '';this._render();}
    set hass(value){this._hass=value;for(const field of Object.values(this._fields || {}))field.hass=value;this._render();}
    _render(){if(!this._config || !this._hass || this._fields)return;this._fields={};
      for(const [key,domain,title] of [['entity','device_tracker','Местоположение автомобиля'],['odometer_entity','sensor','Пробег (необязательно, определяется автоматически)']]){
        const label=document.createElement('label');label.textContent=title;
        const field=document.createElement('ha-selector');field.hass=this._hass;field.selector={entity:{domain}};field.value=this._config[key] || '';field.style.display='block';field.style.marginBottom='16px';this._fields[key]=field;
        field.addEventListener('value-changed',e=>{this._config={...this._config,[key]:e.detail.value || ''};this.dispatchEvent(new CustomEvent('config-changed',{detail:{config:this._config},bubbles:true,composed:true}));});this.append(label,field);
      }
    }
  }
  if(!customElements.get('gwm-jolion-trips-card'))customElements.define('gwm-jolion-trips-card',TripsCard);
  if(!customElements.get('gwm-jolion-trips-card-editor'))customElements.define('gwm-jolion-trips-card-editor',TripsEditor);
  window.customCards=window.customCards || [];window.customCards.push({type:'gwm-jolion-trips-card',name:'GWM Jolion — Поездки',description:'Карта маршрута и пробег за день или период',preview:true});
})();
