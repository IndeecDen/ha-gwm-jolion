const {chromium}=require('playwright');
const path=require('node:path');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try {
  const page=await browser.newPage();
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.setContent('<div></div>');
  for(const name of ['gwm-jolion-card.js','gwm-jolion-remote-card.js','gwm-jolion-alpha20.js']) await page.addScriptTag({path:path.resolve('custom_components/gwm_jolion/frontend',name)});
  const result=await page.evaluate(async()=>{
   const checks=[];
   window.alert=()=>{};
   for(const tag of ['gwm-jolion-card','gwm-jolion-remote-card']){
    const card=document.createElement(tag);document.body.append(card);
    card._render=()=>{};card._config={device_id:'one'};
    const original=card._awaitResponse.bind(card);
    card._awaitResponse=(promise,ms)=>original(promise,Math.min(ms||15000,15));
    let broken=true;
    const entries=['one','two'].map(id=>({device_id:id,config_entry_id:id,entity_id:`button.${id}_refresh`,platform:'gwm_jolion',unique_id:`${id}_refresh`}));
    card._hass={states:{},callWS:async({type})=>{
     if(broken)return new Promise(()=>{});
     return type==='config/entity_registry/list'?entries:[{id:'one'},{id:'two'}];
    }};
    await card._resolveEntities();
    checks.push(!card._resolving && card._resolvedKey===null && !!card._resolveRetryTimer);
    broken=false;
    await card._resolveEntities();
    checks.push(card._entryId==='one');
    card._entities.windowFl='left';card._entities.windowFr='right';
    broken=true;
    await card._resolveEntities();
    checks.push(card._entities.windowFl==='left' && card._entities.windowFr==='right');
    broken=false;
    // Late result for another configured vehicle must never become its mapping.
    let resolveDevices;
    card._hass.callWS=async({type})=>type==='config/entity_registry/list'?entries:new Promise(resolve=>{resolveDevices=resolve;});
    card._resolvedKey=null;
    const pending=card._resolveEntities();
    await new Promise(resolve=>setTimeout(resolve,1));
    card._config={device_id:'two'};
    resolveDevices([{id:'one'},{id:'two'}]);
    await pending;
    checks.push(card._resolvedKey===null && card._entryId==='one');
    card._hass.callWS=async({type})=>type==='config/entity_registry/list'?entries:[{id:'one'},{id:'two'}];
    await card._resolveEntities();
    checks.push(card._entryId==='two');
    let calls=0;
    await card._runBusy('refresh',()=>{calls++;return new Promise(()=>{});});
    checks.push(card._busy.size===0 && calls===1);
    await card._runBusy('refresh',async()=>{calls++;});
    checks.push(card._busy.size===0 && calls===2);
    card.remove();
   }
   return checks;
  });
  assert.equal(result.every(Boolean),true,JSON.stringify(result));
  assert.deepEqual(errors,[]);
  console.log('Both cards: stalled registry recovery, stale vehicle result ignored, busy timeout clears without replay: passed');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
