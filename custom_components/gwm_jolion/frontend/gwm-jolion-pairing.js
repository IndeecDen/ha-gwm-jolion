/* QR decoding is local. jsQR 1.4.0 is bundled under Apache-2.0. */
(() => {
  class Pairing extends HTMLElement {
    connectedCallback() {
      this.attachShadow({mode:'open'}).innerHTML = `<style>
      dialog{box-sizing:border-box;width:min(480px,95vw);max-height:90vh;overflow:auto;border:0;border-radius:16px;background:var(--card-background-color,#fff);color:var(--primary-text-color,#222);font:16px sans-serif}dialog::backdrop{background:#0008}label{display:block;margin:14px 0}input{display:block;box-sizing:border-box;width:100%;padding:10px;font:inherit}button{padding:10px;margin:4px;font:inherit;cursor:pointer}video{width:100%;max-height:250px}p{line-height:1.4}h2{font-size:22px}</style>
      <dialog><h2>Подключить Jolion Locator</h2><p>В приложении нажмите «Показать QR подключения». Сканируйте его или введите ID и ключ вручную.</p>
      <label>ID автомобиля<input id="vehicle" value="jolion" maxlength="40" autocomplete="off"></label>
      <label>Ключ<input id="key" type="password" maxlength="128" autocomplete="off"></label>
      <button id="reveal">Показать ключ</button><label>Фото QR<input id="photo" type="file" accept="image/*"></label>
      <button id="camera">Сканировать камерой</button><button id="stop" hidden>Остановить камеру</button><video playsinline muted hidden></video>
      <p id="status" role="status"></p><button id="save">Подключить</button><button id="close">Закрыть</button></dialog>`;
      this.$('dialog').showModal();
      this.$('dialog').addEventListener('cancel', e => {e.preventDefault();this.remove();});
      this.$('#close').onclick=()=>this.remove();
      this.$('#reveal').onclick=()=>{const k=this.$('#key');k.type=k.type==='password'?'text':'password';this.$('#reveal').textContent=k.type==='password'?'Показать ключ':'Скрыть ключ';};
      this.$('#photo').onchange=()=>this.photo();
      this.$('#camera').onclick=()=>this.camera();
      this.$('#stop').onclick=()=>this.stop();
      this.$('#save').onclick=()=>this.save();
      if(this.initial){this.$('#vehicle').value=this.initial.vehicle_id||'jolion';this.$('#key').value=this.initial.upload_key||'';}
      if(this.onApply)this.$('#save').textContent='Заполнить настройки';
    }
    $(s){return this.shadowRoot.querySelector(s);}
    message(s){this.$('#status').textContent=s;}
    stop(){this._scan=(this._scan||0)+1;clearTimeout(this._timer);this._stream?.getTracks().forEach(t=>t.stop());this._stream=null;const v=this.$('video');v.srcObject=null;v.hidden=true;this.$('#stop').hidden=true;}
    disconnectedCallback(){this.stop();this.$('#key').value='';this.dispatchEvent(new Event('close'));}
    accept(raw){
      if(typeof raw!=='string'||raw.length>2048)throw Error('Неверный QR');
      let id=this.$('#vehicle').value.trim(),key=raw.trim();
      if(key.startsWith('{')){const p=JSON.parse(key);if(p.type!=='golion_locator'||p.version!==1)throw Error('Это не QR Jolion Locator');id=p.vehicle_id;key=p.upload_key;}
      if(typeof id!=='string'||typeof key!=='string'||!/^[a-z0-9_-]{1,40}$/.test(id)||!/^[A-Za-z0-9_-]{32,128}$/.test(key))throw Error('Проверьте ID и ключ: 32–128 букв, цифр, _ или -');
      this.$('#vehicle').value=id;this.$('#key').value=key;this.stop();this.message('Код прочитан. Нажмите «Подключить».');
    }
    decode(source,w,h){
      if(!window.jsQR)throw Error('Сканер загружается. Повторите через несколько секунд.');
      const scale=Math.min(1,1400/Math.max(w,h)),canvas=document.createElement('canvas');canvas.width=Math.max(1,Math.round(w*scale));canvas.height=Math.max(1,Math.round(h*scale));
      const ctx=canvas.getContext('2d',{willReadFrequently:true});ctx.drawImage(source,0,0,canvas.width,canvas.height);const data=ctx.getImageData(0,0,canvas.width,canvas.height);
      return window.jsQR(data.data,data.width,data.height)?.data;
    }
    async photo(){
      this.stop();const file=this.$('#photo').files[0];if(!file)return;
      if(file.size>15*1024*1024){this.message('Выберите изображение до 15 МБ.');return;}
      const url=URL.createObjectURL(file);
      try{const img=new Image();img.src=url;await img.decode();if(!this.isConnected)return;const code=this.decode(img,img.naturalWidth,img.naturalHeight);if(!code)throw Error('QR не найден. Выберите чёткое фото QR крупным планом.');this.accept(code);}
      catch(e){if(this.isConnected)this.message(e.message||'Не удалось прочитать фото');}
      finally{URL.revokeObjectURL(url);this.$('#photo').value='';}
    }
    async camera(){
      this.stop();const serial=this._scan;
      try{
        if(!navigator.mediaDevices?.getUserMedia)throw Error('Камера недоступна. Откройте HA по HTTPS или выберите фото.');
        const stream=await navigator.mediaDevices.getUserMedia({video:{facingMode:{ideal:'environment'}},audio:false});
        if(!this.isConnected||serial!==this._scan){stream.getTracks().forEach(t=>t.stop());return;}
        this._stream=stream;const video=this.$('video');video.hidden=false;video.srcObject=stream;this.$('#stop').hidden=false;await video.play();
        this.message('Наведите камеру на QR на экране автомобиля.');
        const scan=()=>{if(!this.isConnected||serial!==this._scan)return;try{if(video.videoWidth){const code=this.decode(video,video.videoWidth,video.videoHeight);if(code){this.accept(code);return;}}}catch(e){this.message(e.message);}this._timer=setTimeout(scan,300);};scan();
      }catch(e){if(serial===this._scan){this.stop();this.message('Не удалось открыть камеру. Разрешите доступ или выберите фото QR.');}}
    }
    async save(){
      const button=this.$('#save');button.disabled=true;
      try{
        this.accept(JSON.stringify({type:'golion_locator',version:1,vehicle_id:this.$('#vehicle').value.trim(),upload_key:this.$('#key').value.trim()}));
        if(this.onApply){this.onApply({vehicle_id:this.$('#vehicle').value,upload_key:this.$('#key').value});this.remove();return;}
        this.message('Сохраняю подключение…');
        await this.hass.callApi('POST',`gwm_jolion/locator_pairing/${encodeURIComponent(this.entity)}`,{vehicle_id:this.$('#vehicle').value,upload_key:this.$('#key').value});
        this.message('Подключено. ID и ключ сохранены. В приложении укажите внешний HTTPS-адрес HA и начните запись.');
      }catch(e){this.message(e.body?.error==='vehicle_id_in_use'?'Этот ID занят другим автомобилем. Измените ID в приложении.':e.status===403?'Подключение доступно только администратору HA.':e instanceof Error?e.message:'Не удалось подключить. Проверьте права администратора и соединение.');}
      finally{button.disabled=false;}
    }
  }
  customElements.define('gwm-jolion-pairing',Pairing);
  window.gwmJolionPair = (hass,entity,initial,onApply) => {if(document.querySelector('gwm-jolion-pairing'))return;const dialog=document.createElement('gwm-jolion-pairing');dialog.hass=hass;dialog.entity=entity;dialog.initial=initial;dialog.onApply=onApply;document.body.append(dialog);return dialog;};
})();
