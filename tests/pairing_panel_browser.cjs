const {chromium}=require('playwright');
const fs=require('fs'),path=require('path'),assert=require('assert');
// The version comes from the manifest. Writing it out here once loaded the panel at
// one revision and the module it imports at another, so the browser defined the same
// custom element twice - a fixture bug that looked like a card bug.
const VERSION=JSON.parse(fs.readFileSync('custom_components/gwm_jolion/manifest.json','utf8')).version;
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:390,height:844}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/*',route=>{
   const u=new URL(route.request().url());
   if(u.pathname.startsWith('/gwm-jolion/')){
    const name=u.pathname.split('/').pop();
    const file=path.join('custom_components/gwm_jolion/frontend',name==='jsQR.js'?'vendor/jsQR.js':name);
    return route.fulfill({body:fs.readFileSync(file),contentType:'application/javascript'});
   }
   return route.fulfill({contentType:'text/html',body:`<gwm-jolion-pairing-panel></gwm-jolion-pairing-panel><script type="module" src="/gwm-jolion/gwm-jolion-pairing-panel.js?v=${VERSION}"></script><script type="module" src="/gwm-jolion/gwm-jolion-pairing.js?v=${VERSION}"></script>`});
  });
  await page.goto('https://ha.test/gwm-jolion-pairing?entry_id=car');
  await page.waitForFunction(()=>customElements.get('gwm-jolion-pairing-panel'));
  await page.evaluate(()=>{
   window.calls=[];
   document.querySelector('gwm-jolion-pairing-panel').hass={states:{'device_tracker.car':{attributes:{friendly_name:'Мой Jolion'}}},callApi:async(...args)=>calls.push(args),callWS:async()=>[
    {entity_id:'device_tracker.car',platform:'gwm_jolion',config_entry_id:'car'},
    {entity_id:'device_tracker.other',platform:'gwm_jolion',config_entry_id:'other'},
    {entity_id:'device_tracker.foreign',platform:'other',config_entry_id:'car'}]};
  });
  await page.waitForFunction(()=>!document.querySelector('gwm-jolion-pairing-panel').shadowRoot.querySelector('button').disabled);
  assert.equal(await page.locator('select option').count(),1);
  assert.equal(await page.locator('select').inputValue(),'device_tracker.car');
  await page.locator('gwm-jolion-pairing-panel button').click();
  await page.locator('#photo').setInputFiles('tests/fixtures/locator-pairing.png');
  await page.waitForFunction(()=>document.querySelector('gwm-jolion-pairing').shadowRoot.querySelector('#key').value==='a'.repeat(48));
  await page.locator('#save').click();
  assert.equal(await page.evaluate(()=>calls.find(c=>c[0]==='POST')[1]),'gwm_jolion/locator_pairing/device_tracker.car');
  await page.evaluate(()=>document.querySelector('gwm-jolion-pairing-panel').remove());
  assert.equal(await page.locator('gwm-jolion-pairing').count(),0);
  assert.deepStrictEqual(errors,[]);
  console.log('Direct settings URL, selected entry, bundled modules, QR photo save, navigation cleanup: PASS');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});

