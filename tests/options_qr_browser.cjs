const {chromium}=require('playwright');
const fs0=require('fs');
// Read the revision instead of pinning it: the page loads one module by import and
// another by URL, and a mismatched pin makes the browser define both twice.
const VERSION=JSON.parse(fs0.readFileSync('custom_components/gwm_jolion/manifest.json','utf8')).version;
const fs=require('fs'),path=require('path'),assert=require('assert');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:430,height:900}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/*',route=>{
   const u=new URL(route.request().url());
   if(u.pathname.startsWith('/gwm-jolion/')){const n=u.pathname.split('/').pop();return route.fulfill({body:fs.readFileSync(path.join('custom_components/gwm_jolion/frontend',n==='jsQR.js'?'vendor/jsQR.js':n)),contentType:'application/javascript'});}
   return route.fulfill({contentType:'text/html',body:'<body style="font:16px Arial"></body>'});
  });
  await page.goto('https://ha.test');
  // Match HA form public schema/data, .root, child shadow DOM and value-changed contract.
  await page.evaluate(()=>{
   customElements.define('ha-selector',class extends HTMLElement{constructor(){super();this.attachShadow({mode:'open'}).innerHTML='<input>';this.updateComplete=Promise.resolve();}});
   customElements.define('ha-form',class extends HTMLElement{
    constructor(){super();this.attachShadow({mode:'open'});this.data={golion_locator_enabled:false,golion_locator_transport:'https',golion_locator_yandex_public_url:'https://disk.yandex.ru/d/test-folder',golion_locator_vehicle_id:'saved-car',golion_locator_upload_key:'b'.repeat(48)};this.schema=Object.keys(this.data).map(name=>({name}));this.shadowRoot.innerHTML='<div class="root"></div>';for(const schema of this.schema){const field=document.createElement('ha-selector');field.schema=schema;this.shadowRoot.firstChild.append(field);}this.hass={};}
    requestUpdate(){this.updated();}updated(){}
   });
  });
  await page.addScriptTag({url:"/gwm-jolion/gwm-jolion-options.js?v="+VERSION,type:'module'});
  await page.evaluate(()=>{window.form=document.createElement('ha-form');document.body.append(form);form.requestUpdate();});
  assert.equal(await page.getByRole('button',{name:'Ввести с QR'}).isVisible(),false);
  await page.evaluate(()=>{form.data={...form.data,golion_locator_enabled:true};form.requestUpdate();});
  assert.equal(await page.evaluate(()=>[...form.shadowRoot.querySelector('.root').children].find(e=>e.schema.name==='golion_locator_yandex_public_url').style.display),'none');
  await page.evaluate(()=>{form.data.golion_locator_transport='yandex_disk';form.requestUpdate();});
  assert.equal(await page.evaluate(()=>[...form.shadowRoot.querySelector('.root').children].find(e=>e.schema.name==='golion_locator_yandex_public_url').style.display),'block');
  await page.evaluate(()=>{form.data.golion_locator_transport='https';form.requestUpdate();});
  await page.getByRole('button',{name:'Ввести с QR'}).click();
  assert.equal(await page.locator('#vehicle').inputValue(),'saved-car');assert.equal(await page.locator('#key').inputValue(),'b'.repeat(48));
  await page.locator('#vehicle').fill('new-car');await page.locator('#key').fill('c'.repeat(48));await page.locator('#save').click();
  assert.equal(await page.evaluate(()=>form.data.golion_locator_vehicle_id),'new-car');
  assert.equal(await page.evaluate(()=>form.data.golion_locator_upload_key),'c'.repeat(48));
  await page.getByRole('button',{name:'Ввести с QR'}).click();
  assert.equal(await page.locator('#vehicle').inputValue(),'new-car');assert.equal(await page.locator('#key').inputValue(),'c'.repeat(48));
  await page.locator('#photo').setInputFiles('tests/fixtures/locator-pairing.png');
  await page.waitForFunction(()=>document.querySelector('gwm-jolion-pairing').shadowRoot.querySelector('#key').value==='a'.repeat(48));
  await page.locator('#save').click();assert.equal(await page.evaluate(()=>form.data.golion_locator_vehicle_id),'jolion');
  await page.evaluate(()=>{form.data={...form.data,golion_locator_enabled:false};form.requestUpdate();});
  assert.equal(await page.getByRole('button',{name:'Ввести с QR'}).isVisible(),false);
  assert.equal(await page.evaluate(()=>form.data.golion_locator_upload_key),'a'.repeat(48));
  assert.deepStrictEqual(errors,[]);console.log('Options checkbox visibility, inline QR, saved ID/key, reopen, scan and transfer: PASS');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});



