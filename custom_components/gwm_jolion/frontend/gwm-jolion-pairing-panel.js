import './jsQR.js?v=1.4.0';
import './gwm-jolion-pairing.js?v=0.2.0-beta.4';

class JolionPairingPanel extends HTMLElement {
  constructor() {
    super();this.attachShadow({mode:'open'});
    this.shadowRoot.innerHTML=`<style>
      :host{display:block;height:100%;overflow:auto;background:var(--primary-background-color,#fafafa);color:var(--primary-text-color,#222)}
      main{max-width:560px;margin:32px auto;padding:24px;font:16px sans-serif;line-height:1.5}
      h1{font-size:26px}label{display:block;margin:24px 0}select,button{box-sizing:border-box;font:inherit;padding:12px;border-radius:8px;border:1px solid #999;background:var(--card-background-color,#fff);color:inherit;width:100%}button{cursor:pointer}a{color:var(--primary-color,#03a9f4)}
    </style><main><a href="/config/integrations/integration/gwm_jolion">← Настройки GWM Jolion</a><h1>Подключение Jolion Locator</h1>
    <p>В приложении автомобиля нажмите «Показать QR подключения». Здесь можно прочитать QR камерой, выбрать его фотографию или ввести ключ вручную.</p>
    <label>Автомобиль<select aria-label="Автомобиль"></select></label><button disabled>Открыть камеру / фото QR / ввод ключа</button><p role="status"></p>
    <p>После подключения Locator включится автоматически. Карта поездок для подключения не требуется.</p></main>`;
    this.shadowRoot.querySelector('button').onclick=async()=>{
      const entity=this.shadowRoot.querySelector('select').value;
      if(entity){try{const initial=await this._hass.callApi('GET',`gwm_jolion/locator_pairing/${encodeURIComponent(entity)}`);window.gwmJolionPair(this._hass,entity,initial);}catch(e){this.shadowRoot.querySelector('[role=status]').textContent='Не удалось прочитать настройки автомобиля. Проверьте права администратора.';}}
    };
  }
  set hass(value){this._hass=value;if(this.isConnected)this.load();}
  connectedCallback(){this.load();}
  disconnectedCallback(){document.querySelector('gwm-jolion-pairing')?.remove();}
  async load(){
    if(!this._hass||this._loading||this._loaded)return;
    this._loading=true;
    const select=this.shadowRoot.querySelector('select'),status=this.shadowRoot.querySelector('[role=status]');
    try{
      const entries=await this._hass.callWS({type:'config/entity_registry/list'});
      const entryId=new URLSearchParams(window.location.search).get('entry_id');
      const vehicles=entries.filter(e=>e.platform==='gwm_jolion'&&e.entity_id.startsWith('device_tracker.')&&!e.disabled_by&&(!entryId||e.config_entry_id===entryId));
      select.replaceChildren();
      for(const e of vehicles){const option=document.createElement('option');option.value=e.entity_id;option.textContent=this._hass.states[e.entity_id]?.attributes.friendly_name||e.name||e.original_name||e.entity_id;select.append(option);}
      this.shadowRoot.querySelector('button').disabled=!vehicles.length;
      status.textContent=vehicles.length?'':'Трекер автомобиля не найден. Проверьте, что интеграция загружена и сущность device_tracker включена, затем обновите страницу.';
      this._loaded=true;
    }catch(e){status.textContent='Не удалось получить список автомобилей. Обновите страницу и войдите как администратор HA.';}
    finally{this._loading=false;}
  }
}
customElements.define('gwm-jolion-pairing-panel',JolionPairingPanel);

