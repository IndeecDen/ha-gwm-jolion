const {chromium}=require('playwright');
const path=require('node:path');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try {
  const page=await browser.newPage({viewport:{width:430,height:1100}});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  page.on('dialog',dialog=>dialog.accept());
  await page.setContent('<style>body{margin:0;--primary-color:#03a9f4;--primary-text-color:#ddd;--secondary-text-color:#aaa;--card-background-color:#292929;--secondary-background-color:#273237;background:#222;color:#ddd;font-family:Arial}gwm-jolion-card{display:block}</style><gwm-jolion-card id="first"></gwm-jolion-card>');
  for(const name of ['gwm-jolion-card.js','gwm-jolion-alpha20.js']) await page.addScriptTag({path:path.resolve('custom_components/gwm_jolion/frontend',name)});
  await page.evaluate(()=>{
   window.calls=[];
   window.defaults={temperature:22,climate_time:15,engine_time:15,climate_enabled:true,driver_enabled:true,passenger_enabled:true,driver:3,passenger:3,seat_time:5};
   window.saved={card_settings:{},preparation_profiles:[{id:'winter',name:'Зима',settings:{...defaults,temperature:26,seat_time:10}},{id:'summer',name:'Лето',settings:{...defaults,temperature:20,driver_enabled:false,passenger_enabled:false}}]};
   window.renderAll=()=>document.querySelectorAll('gwm-jolion-card').forEach(c=>{
    c._hass.states['button.refresh']={state:'unknown',attributes:structuredClone(saved)};c._render();
   });
   window.mount=c=>{
    c.setConfig({confirm_controls:false});c._entryId='car-1';c._resolvedKey='|';
    c._entities.refresh='button.refresh';c._entities.engine='binary_sensor.engine';
    c._hass={states:{'binary_sensor.engine':{state:'off',attributes:{}}},callService:async(domain,service,data)=>{
     calls.push([domain,service,structuredClone(data)]);
     if(service==='save_card_settings') Object.assign(saved.card_settings,data.settings);
     if(service==='manage_preparation_profile'){
      const p=saved.preparation_profiles.find(p=>p.id===data.profile_id);
      if(data.action==='select') saved.card_settings={...saved.card_settings,...(p?{...p.settings,comfort_start:true}:{}),selected_profile:data.profile_id};
      if(data.action==='update'){p.name=data.name;p.settings=structuredClone(data.settings);}
      if(data.action==='create'||data.action==='copy'){
       const n={id:`new-${calls.length}`,name:data.name,settings:structuredClone(data.action==='copy'?p.settings:data.settings)};
       saved.preparation_profiles.push(n);saved.card_settings={...saved.card_settings,...n.settings,selected_profile:n.id,comfort_start:true};
      }
      if(data.action==='delete'){
       saved.preparation_profiles=saved.preparation_profiles.filter(item=>item.id!==data.profile_id);
       if(saved.card_settings.selected_profile===data.profile_id)saved.card_settings.selected_profile='';
      }
     }
     renderAll();
    }};
    renderAll();
   };
   mount(document.querySelector('#first'));
  });
  const first=page.locator('#first');
  const choose=()=>first.getByLabel('Профиль подготовки');
  await choose().selectOption('winter');
  assert.equal(await first.locator('[data-profile-status]').innerText(),'Сохранён');
  assert.match(await first.locator('[data-profile-summary]').innerText(),/26 °C/);
  await first.getByRole('button',{name:'Настроить',exact:true}).click();
  const slide=async(label,value)=>first.getByLabel(label,{exact:true}).evaluate((el,v)=>{el.value=v;el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));},String(value));
  await slide('Профиль: Температура',25);
  assert.equal(await first.locator('[data-profile-status]').innerText(),'Изменён');
  assert.equal(await page.evaluate(()=>saved.preparation_profiles[0].settings.temperature),26);
  await first.getByRole('button',{name:'Вернуть сохранённое'}).click();
  assert.equal(await first.getByLabel('Профиль: Температура',{exact:true}).inputValue(),'26');
  await first.getByLabel('Название профиля',{exact:true}).fill('Мой <профиль>');
  await first.getByRole('button',{name:'Сохранить как новый'}).click();
  assert.equal(await choose().locator('option:checked').innerText(),'Мой <профиль>');
  await first.getByLabel('Название профиля',{exact:true}).fill('Утро');
  await slide('Профиль: Время двигателя',20);
  await first.getByLabel('Включать климат при подготовке',{exact:true}).uncheck();
  await first.getByLabel('Подогрев пассажира',{exact:true}).uncheck();
  await first.getByRole('button',{name:'Сохранить изменения'}).click();
  assert.equal(await first.locator('[data-profile-status]').innerText(),'Сохранён');
  assert.equal(await choose().locator('option:checked').innerText(),'Утро');
  assert.equal(await page.evaluate(()=>calls.some(c=>!['save_card_settings','manage_preparation_profile'].includes(c[1]))),false);
  await first.getByRole('button',{name:'Запустить подготовку',exact:true}).click();
  const launch=await page.evaluate(()=>calls.find(c=>c[1]==='start_with_comfort'));
  assert.equal(launch[2].entry_id,'car-1');assert.equal(launch[2].engine_time,20);
  assert.equal(launch[2].climate_enabled,false);assert.equal(launch[2].driver,3);assert.equal(launch[2].passenger,0);
  // A fresh card/device restores the server snapshot without sending any command.
  await page.evaluate(()=>{window.beforeMount=calls.length;const c=document.createElement('gwm-jolion-card');c.id='second';document.body.append(c);mount(c);});
  assert.equal(await page.locator('#second').getByLabel('Профиль подготовки').locator('option:checked').innerText(),'Утро');
  assert.equal(await page.evaluate(()=>calls.length===beforeMount),true);
  await first.getByRole('button',{name:'Копировать',exact:true}).click();
  assert.equal(await choose().locator('option:checked').innerText(),'Утро — копия');
  await first.getByRole('button',{name:'Удалить',exact:true}).click();
  assert.equal(await choose().inputValue(),'');
  assert.equal(await choose().locator('option').count(),4);
  await choose().selectOption('winter');
  await page.evaluate(()=>document.querySelector('#second').remove());
  for(const width of [280,430,760]){
   await page.setViewportSize({width,height:1100});
   assert.equal(await first.evaluate(c=>c.shadowRoot.querySelector('.preparation').scrollWidth<=c.shadowRoot.querySelector('.preparation').clientWidth),true);
  }
  await page.setViewportSize({width:430,height:1100});
  await page.screenshot({path:process.env.TEMP+'/gwm-profile-card.png',fullPage:true});
  await first.locator('.preparation').screenshot({path:process.env.TEMP+'/gwm-preparation-panel.png'});
  await page.evaluate(()=>{const c=document.querySelector('#first');c._hass.states['binary_sensor.engine'].state='unavailable';c._render();});
  assert.equal(await first.getByRole('button',{name:'Запустить подготовку',exact:true}).isDisabled(),true);
  assert.deepEqual(errors,[]);
  console.log('Profiles: select, draft, revert, create, rename, update, copy, delete, restart, narrow layout, guarded launch: passed');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
