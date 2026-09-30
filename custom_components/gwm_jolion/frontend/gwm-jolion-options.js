import './jsQR.js?v=1.4.0';
import './gwm-jolion-pairing.js?v=0.2.0-beta.6';

// HA's form schema has no custom button selector. Augment only our three
// uniquely named fields; all values and persistence remain in the options flow.
const ENABLED='golion_locator_enabled',ID='golion_locator_vehicle_id',KEY='golion_locator_upload_key';
function enhance(form){
  if(!Array.isArray(form.schema)||![ENABLED,ID,KEY].every(n=>form.schema.some(s=>s.name===n)))return;
  const root=form.shadowRoot?.querySelector('.root');if(!root)return;
  const fields=[...root.children],id=fields.find(e=>e.schema?.name===ID),key=fields.find(e=>e.schema?.name===KEY);
  const enabled=Boolean(form.data?.[ENABLED]??form.schema.find(s=>s.name===ENABLED)?.default);
  for(const field of [id,key]){if(field)field.style.setProperty('display',enabled?'block':'none','important');}
  for(const field of fields){
    if(field.schema?.name==='golion_locator_transport')field.style.setProperty('display',enabled?'block':'none','important');
    if(field.schema?.name==='golion_locator_yandex_public_url'){
      const mode=form.data?.golion_locator_transport??form.schema.find(s=>s.name==='golion_locator_transport')?.default;
      field.style.setProperty('display',enabled&&mode==='yandex_disk'?'block':'none','important');
    }
  }
  if(!key?.shadowRoot)return;
  let button=key.shadowRoot.querySelector('[data-gwm-qr]');
  if(!button){
    button=document.createElement('button');button.type='button';button.dataset.gwmQr='';button.textContent='Ввести с QR';
    button.style.cssText='display:block;margin-top:12px;padding:10px 16px;border:1px solid var(--divider-color,#888);border-radius:8px;background:var(--secondary-background-color,#eee);color:var(--primary-text-color,#222);font:inherit;cursor:pointer';
    key.shadowRoot.append(button);
    button.onclick=()=>{
      const value=name=>form.data?.[name]??form.schema.find(s=>s.name===name)?.default??'';
      const dialog=window.gwmJolionPair(form.hass,null,{vehicle_id:value(ID),upload_key:value(KEY)},values=>{
        if(!form.isConnected)return;
        form.data={...form.data,[ENABLED]:true,[ID]:values.vehicle_id,[KEY]:values.upload_key};
        form.dispatchEvent(new CustomEvent('value-changed',{detail:{value:form.data},bubbles:true,composed:true}));
        form.requestUpdate?.();
      });
      // Keep the existing options form behind the modal; no reload or second save path.
      if(dialog){const observer=new MutationObserver(()=>{if(!form.isConnected){dialog.remove();observer.disconnect();}});observer.observe(form.getRootNode(),{childList:true,subtree:true});dialog.addEventListener('close',()=>observer.disconnect(),{once:true});}
    };
  }
}
customElements.whenDefined('ha-form').then(()=>{
  const proto=customElements.get('ha-form').prototype;
  if(proto._gwmLocatorOptions)return;
  proto._gwmLocatorOptions=true;
  const updated=proto.updated;
  proto.updated=function(changed){updated?.call(this,changed);enhance(this);const key=[...(this.shadowRoot?.querySelector('.root')?.children||[])].find(e=>e.schema?.name===KEY);key?.updateComplete?.then(()=>enhance(this));};
});

