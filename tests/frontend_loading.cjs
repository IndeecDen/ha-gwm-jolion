// Cold dashboard startup: wait for module resources before constructing cards.
const {chromium}=require('playwright');
const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');
const root=path.resolve('custom_components/gwm_jolion/frontend');
const files=['gwm-jolion-card.js','gwm-jolion-card-editor.js','gwm-jolion-remote-card.js','gwm-jolion-trips-card.js','gwm-jolion-alpha20.js'];
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
  const page=await browser.newPage(),errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  await page.route('**/*',async route=>{
   const name=new URL(route.request().url()).pathname.split('/').at(-1);
   if(files.includes(name)){
    // Longer than Lovelace's 2-second custom-element grace period.
    if(name==='gwm-jolion-card.js')await new Promise(resolve=>setTimeout(resolve,2200));
    return route.fulfill({body:fs.readFileSync(path.join(root,name)),contentType:'application/javascript'});
   }
   return route.fulfill({body:'<html><body></body></html>',contentType:'text/html'});
  });
  for(let reload=0;reload<2;reload++){
   await page.goto('http://gwm.test');
   const result=await page.evaluate(async files=>{
    const tags=['gwm-jolion-card','gwm-jolion-remote-card','gwm-jolion-trips-card'];
    const initial=tags.map(tag=>!!customElements.get(tag));
    await Promise.all(files.map(file=>import(`/gwm-jolion/${file}?v=test`)));
    const cards=tags.map(tag=>{
     const card=document.createElement(tag);
     card.setConfig({type:`custom:${tag}`,entity:'device_tracker.test',map_style:'osm'});
     document.body.append(card);
     return {tag,ready:!!card.shadowRoot,config:card._config.entity};
    });
    return {initial,cards,patched:!!customElements.get('gwm-jolion-card').prototype.__gwmAlpha20Common};
   },files);
   assert.deepEqual(result.initial,[false,false,false]);
   assert(result.cards.every(card=>card.ready&&card.config==='device_tracker.test'));
   assert(result.patched);
  }
  assert.deepEqual(errors,[]);
  console.log('Cold reload: delayed parallel Lovelace modules register all three cards before construction: PASS');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exit(1);});
