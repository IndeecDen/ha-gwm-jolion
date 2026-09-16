const {chromium}=require('playwright');
const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
  const page=await browser.newPage({viewport:{width:430,height:1050}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/*',async route=>{
   const url=new URL(route.request().url());
   if(url.hostname==='tile.openstreetmap.org')return route.fulfill({status:200,contentType:'image/png',body:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=','base64')});
   if(url.pathname.startsWith('/gwm-jolion/')){
    const file=path.resolve('custom_components/gwm_jolion/frontend',url.pathname.slice('/gwm-jolion/'.length));
    return route.fulfill({body:fs.readFileSync(file),contentType:file.endsWith('.css')?'text/css':'application/javascript'});
   }
   return route.fulfill({body:'<style>body{margin:0;background:#18232a;color:#dde6ed;font-family:Arial;--primary-color:#039ecc;--primary-text-color:#dde6ed;--secondary-text-color:#a4b4c0;--secondary-background-color:#28363d}ha-card{display:block;background:#223039}</style><gwm-jolion-trips-card></gwm-jolion-trips-card>'});
  });
  await page.goto('http://gwm.test');
  await page.addScriptTag({path:path.resolve('custom_components/gwm_jolion/frontend/gwm-jolion-trips-card.js')});
  await page.evaluate(()=>{customElements.define('ha-icon',class extends HTMLElement{connectedCallback(){this.textContent=this.getAttribute('icon')==='mdi:counter'?'◉':'▦';}});});
  await page.evaluate(()=>{
   window.calls=[];window.card=document.querySelector('gwm-jolion-trips-card');
   window.sample={km:14.6,method:'odometer',samples:20,timezone:'Europe/Moscow',retention_days:90,last:1789570800,days:[{date:'2026-09-16',km:14.6,method:'odometer',gaps:1}],segments:[[[55.75,37.60],[55.752,37.61],[55.759,37.62]],[[55.763,37.63],[55.768,37.64]]]};
   window.hass={config:{time_zone:'Europe/Moscow'},states:{},callWS:async msg=>{calls.push(msg);return structuredClone(sample);}};
   card.setConfig({entity:'device_tracker.test',title:'Поездки · Jolion'});card.hass=hass;
  });
  await page.waitForFunction(()=>card._map && card._layer.getLayers().length===4);
  assert.match(await page.locator('.km').textContent(),/14,6/);
  await page.locator('[data-mode="yesterday"]').click();
  await page.waitForFunction(()=>document.querySelector('gwm-jolion-trips-card').shadowRoot.querySelector('[data-mode="yesterday"]').classList.contains('active'));
  assert.equal(await page.locator('.dates').isVisible(),false);
  assert.equal(await page.locator('h2,details,.notice,.coverage').count(),0);
  assert(await page.locator('.map').evaluate(el=>el.getBoundingClientRect().bottom) <= await page.locator('.summary').evaluate(el=>el.getBoundingClientRect().top));
  await page.locator('#calendar').click();
  await page.locator('#start').fill('2026-09-01');await page.locator('#end').fill('2026-09-16');await page.locator('#show').click();
  await page.waitForFunction(()=>calls.at(-1).start==='2026-09-01' && calls.at(-1).end==='2026-09-16');
  assert.equal(await page.locator('.dates').isVisible(),false);
  assert.match(await page.locator('#calendar').getAttribute('class'),/active/);
  await page.screenshot({path:path.join(process.env.TEMP,'gwm-trips-card.png'),fullPage:true});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  await page.evaluate(()=>{sample={...sample,samples:0,days:[],segments:[],last:null};card._load();});
  await page.waitForFunction(()=>card.shadowRoot.querySelector('.error').textContent.includes('нет записей'));
  assert.equal(await page.evaluate(()=>card._layer.getLayers().length),0);
  await page.evaluate(()=>{hass.callWS=async()=>{throw Error('Нет доступа');};card._load();});
  await page.waitForFunction(()=>card.shadowRoot.querySelector('.error').textContent==='Нет доступа');
  await page.evaluate(()=>{window.saved=card;card.remove();});
  assert.deepEqual(errors,[]);
  console.log('Trips card: route, calendar, mobile layout, empty history and errors passed');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
