const {chromium}=require('playwright');
const path=require('node:path');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try {
 const page=await browser.newPage({viewport:{width:430,height:1000}});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.setContent('<gwm-jolion-card></gwm-jolion-card>');
 for(const name of ['gwm-jolion-card.js','gwm-jolion-alpha20.js']) await page.addScriptTag({path:path.resolve('custom_components/gwm_jolion/frontend',name)});
 await page.evaluate(()=>{
  window.calls=[];
  const c=document.querySelector('gwm-jolion-card');
  c.setConfig({});c._entryId='car-2';c._resolvedKey='|';
  c._hass={states:{},callService:async(...args)=>window.calls.push(args)};
  c._render();
 });
 const driver=page.getByLabel('Подогрев: Водитель');
 const slide=async(locator,value)=>locator.evaluate((el,v)=>{el.value=v;el.dispatchEvent(new Event('input',{bubbles:true}));},value);
 await slide(driver,'3');
 await slide(page.getByLabel('Подогрев: Пассажир'),'1');
 await slide(page.getByLabel('Таймер подогрева'),'7');
 await page.getByLabel('Таймер подогрева').press('Tab');
 await page.getByRole('button',{name:/Применить/}).click();
 assert.deepEqual(await page.evaluate(()=>window.calls.find(call=>call[1]==='set_seat_heating')),['gwm_jolion','set_seat_heating',{entry_id:'car-2',operation_time:7,driver:3,passenger:1}]);
 assert.equal(await driver.inputValue(),'3');
 await page.evaluate(()=>{const c=document.querySelector('gwm-jolion-card');c._entities.seatDriver='sensor.driver';c._hass.states['sensor.driver']={state:'2',attributes:{}};c._render();});
 assert.match(await page.locator('[data-seat-status="driver"]').innerText(),/Включён · уровень 2/);
 await page.evaluate(()=>{const c=document.querySelector('gwm-jolion-card');c._hass.states['sensor.driver'].state='0';c._render();});
 assert.equal(await page.locator('[data-seat-status="driver"]').innerText(),'Выключен');
 assert.equal(await page.getByRole('button',{name:/Обогрев руля|Обогрев заднего стекла/}).count(),0);

 await page.getByLabel('Включить: Пассажир').uncheck();
 assert.equal(await page.getByLabel('Подогрев: Пассажир').isDisabled(),true);
 await page.getByRole('button',{name:/Применить/}).click();
 assert.equal(await page.evaluate(()=>window.calls.filter(call=>call[1]==='set_seat_heating').at(-1)[2].passenger),0);
 assert.equal(await page.locator('gwm-jolion-card').locator('button').filter({hasText:'Окна'}).count(),1);
 await page.evaluate(()=>{const c=document.querySelector('gwm-jolion-card');c._entities.engine='sensor.engine';c._hass.states['sensor.engine']={state:'off',attributes:{}};c._config.confirm_controls=false;c._render();});
 await page.locator('#comfort-start').check();
 const before=await page.evaluate(()=>window.calls.filter(call=>call[1]!=="save_card_settings").length);
 await page.locator('[data-temp-step="1"]').click();
 assert.equal(await page.evaluate(()=>window.calls.filter(call=>call[1]!=="save_card_settings").length),before);
 await page.locator('[data-action="engine"]').click();
 const launch=await page.evaluate(()=>window.calls.filter(call=>call[1]!=="save_card_settings").at(-1));
 assert.equal(launch[1],'start_with_comfort');assert.equal(launch[2].temperature,23);assert.equal(launch[2].passenger,0);
 await page.evaluate(()=>{
   const c=document.querySelector('gwm-jolion-card');c._entities.refresh='button.refresh';
   c._hass.states['button.refresh']={state:'unknown',attributes:{card_settings:{temperature:26,climate_time:20,engine_time:25,driver:2,passenger:1,seat_time:9,driver_enabled:true,passenger_enabled:false,comfort_start:true}}};
   window.beforeRestore=window.calls.length;c._render();
 });
 assert.equal(await page.getByLabel('Подогрев: Водитель').inputValue(),'2');
 assert.equal(await page.getByLabel('Таймер подогрева').inputValue(),'9');
 assert.equal(await page.getByLabel('Включить: Пассажир').isChecked(),false);
 assert.equal(await page.evaluate(()=>window.calls.length===window.beforeRestore),true);
 await page.evaluate(()=>{const c=document.querySelector('gwm-jolion-card');c._entryId='another-car';c._entities.refresh='button.other';c._hass.states['button.other']={state:'unknown',attributes:{card_settings:{}}};c._render();});
 assert.equal(await page.getByLabel('Таймер подогрева').inputValue(),'5');
 assert.equal(await page.locator('#comfort-start').isChecked(),false);
 await page.screenshot({path:process.env.TEMP+'/gwm-seat-card.png',fullPage:true});
 assert.deepEqual(errors,[]);
 console.log('Seat controls, timer validation, rerender persistence, vehicle targeting, window control: passed');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
