/* GWM Jolion Trips Card v0.1.0-beta.11 */
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
        :host{display:block}ha-card{overflow:hidden}.content{padding:20px}h2{margin:0 0 16px;font-size:22px;font-weight:600}
        .shortcuts,.dates,.summary{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
        button,input{font:inherit;color:var(--primary-text-color);border:1px solid var(--divider-color,#8885);border-radius:12px;background:var(--secondary-background-color,#eee);padding:10px 12px;box-sizing:border-box}
        button{cursor:pointer}button.active{background:var(--primary-color,#03a9f4);color:white;border-color:transparent}
        button:focus-visible,input:focus-visible{outline:2px solid var(--primary-color,#03a9f4);outline-offset:2px}
        .dates{margin:14px 0}label{display:flex;flex:1;min-width:130px;flex-direction:column;gap:5px;color:var(--secondary-text-color);font-size:12px}input{width:100%;color-scheme:light dark}
        .summary{justify-content:space-between;margin:18px 0 8px}.km{font-size:32px;font-weight:600}.method,.notice,.error,.coverage{font-size:13px;color:var(--secondary-text-color);line-height:1.5}
        .error{color:var(--error-color,#db4437)}.map{height:380px;background:#e9edef;z-index:0}.notice{margin-top:10px}.coverage{margin-top:6px}
        details{margin-top:14px}summary{cursor:pointer}.day{display:flex;justify-content:space-between;padding:7px 0;border-bottom:1px solid var(--divider-color,#8883)}
        .leaflet-container{font-family:inherit}.leaflet-control-attribution{font-size:10px}
        @media(max-width:400px){.content{padding:14px}.map{height:320px}}
      </style><ha-card><div class="content"><h2></h2>
      <div class="shortcuts"><button data-mode="today">Сегодня</button><button data-mode="yesterday">Вчера</button><button data-mode="week">7 дней</button></div>
      <div class="dates"><label>С<input type="date" id="start"></label><label>По<input type="date" id="end"></label><button id="show">Показать</button></div>
      <div class="summary"><div><div class="km">— км</div><div class="method"></div></div><button id="refresh" aria-label="Обновить историю">↻ Обновить</button></div>
      <div class="error" role="status"></div><div class="coverage"></div><div class="map-status notice" role="status"></div></div><div class="map" aria-label="Карта маршрута"></div>
      <div class="content"><div class="notice">По записанным данным: начало и конец дня, пропуски связи и редкий опрос могут уменьшать учтённый пробег. История накапливается после установки.</div>
      <details><summary>Пробег по дням</summary><div class="days"></div></details></div></ha-card>`;
      this.shadowRoot.querySelectorAll('[data-mode]').forEach(button => button.onclick=()=>{this._mode=button.dataset.mode;this._load();});
      this.shadowRoot.querySelector('#show').onclick=()=>{this._mode='custom';this._load();};
      this.shadowRoot.querySelector('#refresh').onclick=()=>this._load();
      for(const id of ['start','end']) this.shadowRoot.querySelector('#'+id).onchange=()=>{this._mode='custom';this._highlight();};
    }
    setConfig(config) {
      this._config={...config}; this._serial++;this._fitKey=null;
      this.shadowRoot.querySelector('h2').textContent=config.title || 'Поездки';
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
    getCardSize(){return 9;}
    _highlight(){this.shadowRoot.querySelectorAll('[data-mode]').forEach(b=>b.classList.toggle('active',b.dataset.mode===this._mode));}
    async _load(){
      if(!this.isConnected || !this._hass || !this._config)return;
      const serial=++this._serial;
      const root=this.shadowRoot, error=root.querySelector('.error');
      this._layer?.clearLayers();root.querySelector('.km').textContent='— км';root.querySelector('.days').replaceChildren();root.querySelector('.coverage').textContent='';root.querySelector('.method').textContent='';
      if(!this._config.entity){error.textContent='Выберите сущность местоположения GWM Jolion в настройках карточки.';return;}
      const today=dateInZone(this._hass.config.time_zone);
      if(this._mode!=='custom'){
        root.querySelector('#end').value=this._mode==='yesterday'?shift(today,-1):today;
        root.querySelector('#start').value=this._mode==='week'?shift(today,-6):root.querySelector('#end').value;
      }
      const start=root.querySelector('#start').value,end=root.querySelector('#end').value;
      this._highlight();
      if(!start || !end || start>end){error.textContent='Проверьте начало и конец периода.';return;}
      error.textContent='Загрузка истории…';
      let timeout;
      try{
        const data=await Promise.race([this._hass.callWS({type:'gwm_jolion/trips',entity_id:this._config.entity,start,end}),new Promise((_,reject)=>{timeout=setTimeout(()=>reject(new Error('История не ответила. Нажмите «Обновить».')),20000);})]);
        if(serial!==this._serial || !this.isConnected)return;
        error.textContent=data.samples?'':'За этот период нет записей.';
        root.querySelector('.km').textContent=data.samples?`${data.method==='odometer'?'':'≈ '}${data.km.toLocaleString('ru-RU')} км`:'— км';
        root.querySelector('.method').textContent=data.samples?(data.method==='odometer'?'По одометру':data.method==='gps'?'Оценка по GPS':'Одометр и оценка по GPS'):'';
        root.querySelector('.coverage').textContent=`Часовой пояс: ${data.timezone} · Хранение: ${data.retention_days} дней`+(data.last?` · Последняя запись: ${new Date(data.last*1000).toLocaleString('ru-RU',{timeZone:data.timezone})}`:'');
        for(const day of data.days){const row=document.createElement('div');row.className='day';const label=document.createElement('span'),value=document.createElement('span');label.textContent=day.date;value.textContent=`${day.method==='gps'?'≈ ':''}${day.km} км${day.gaps?' · есть пропуски':''}`;row.append(label,value);root.querySelector('.days').append(row);}
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
      finally{clearTimeout(timeout);}
    }
  }
  class TripsEditor extends HTMLElement{
    setConfig(config){this._config=config;if(this._selector)this._selector.value=config.entity || '';this._render();}
    set hass(value){this._hass=value;if(this._selector)this._selector.hass=value;else this._render();}
    _render(){if(!this._config || !this._hass || this._selector)return;
      const label=document.createElement('label');label.textContent='Местоположение автомобиля';
      this._selector=document.createElement('ha-selector');this._selector.hass=this._hass;
      this._selector.selector={entity:{domain:'device_tracker'}};this._selector.value=this._config.entity || '';
      this._selector.addEventListener('value-changed',e=>{this._config={...this._config,entity:e.detail.value};this.dispatchEvent(new CustomEvent('config-changed',{detail:{config:this._config},bubbles:true,composed:true}));});this.append(label,this._selector);
    }
  }
  if(!customElements.get('gwm-jolion-trips-card'))customElements.define('gwm-jolion-trips-card',TripsCard);
  if(!customElements.get('gwm-jolion-trips-card-editor'))customElements.define('gwm-jolion-trips-card-editor',TripsEditor);
  window.customCards=window.customCards || [];window.customCards.push({type:'gwm-jolion-trips-card',name:'GWM Jolion — Поездки',description:'Карта маршрута и пробег за день или период',preview:true});
})();
