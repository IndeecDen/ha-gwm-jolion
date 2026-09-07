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
 await driver.selectOption('3');
 await page.getByLabel('Подогрев: Пассажир').selectOption('1');
 await page.getByLabel('Таймер подогрева').fill('7');
 await page.getByLabel('Таймер подогрева').press('Tab');
 await page.getByRole('button',{name:/Применить подогрев/}).click();
 assert.deepEqual(await page.evaluate(()=>window.calls[0]),['gwm_jolion','set_seat_heating',{entry_id:'car-2',operation_time:7,driver:3,passenger:1}]);
 assert.equal(await driver.inputValue(),'3');
 await page.getByLabel('Таймер подогрева').fill('99');await page.getByLabel('Таймер подогрева').press('Tab');
 assert.equal(await page.getByLabel('Таймер подогрева').inputValue(),'7');
 assert.equal(await page.locator('gwm-jolion-card').locator('button').filter({hasText:'Окна'}).count(),1);
 await page.screenshot({path:process.env.TEMP+'/gwm-seat-card.png',fullPage:true});
 assert.deepEqual(errors,[]);
 console.log('Seat controls, timer validation, rerender persistence, vehicle targeting, window control: passed');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
