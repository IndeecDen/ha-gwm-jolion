const {chromium}=require('playwright');
const fs=require('fs'),path=require('path'),assert=require('assert');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:390,height:844}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/*',route=>route.fulfill({contentType:'text/html',body:'<body></body>'}));
  await page.goto('https://pair.test');
  await page.addScriptTag({path:'custom_components/gwm_jolion/frontend/vendor/jsQR.js',type:'module'});
  await page.addScriptTag({path:'custom_components/gwm_jolion/frontend/gwm-jolion-pairing.js'});
  const open=()=>page.evaluate(()=>{window.calls=[];window.gwmJolionPair({callApi:async(...args)=>calls.push(args)},'device_tracker.car');});
  await open();
  await page.locator('#photo').setInputFiles(path.resolve('tests/fixtures/locator-pairing.png'));
  await page.waitForFunction(()=>document.querySelector('gwm-jolion-pairing').shadowRoot.querySelector('#key').value==='a'.repeat(48));
  await page.locator('#save').click();
  await page.waitForFunction(()=>window.calls.length===1);
  assert.deepStrictEqual(await page.evaluate(()=>calls[0]),['POST','gwm_jolion/locator_pairing/device_tracker.car',{vehicle_id:'jolion',upload_key:'a'.repeat(48)}]);
  assert.equal(await page.locator('#key').inputValue(),'a'.repeat(48));
  await page.locator('#close').click();await open();
  await page.locator('#vehicle').fill('manual');await page.locator('#key').fill('b'.repeat(48));await page.locator('#save').click();
  assert.equal(await page.evaluate(()=>calls[0][2].vehicle_id),'manual');
  await page.locator('#close').click();await open();
  await page.evaluate(()=>{
    window.stops=0;
    Object.defineProperty(navigator.mediaDevices,'getUserMedia',{configurable:true,value:async()=>new Promise(resolve=>window.resolveCamera=()=>resolve({getTracks:()=>[{stop:()=>stops++}]}))});
  });
  await page.locator('#camera').click();await page.locator('#close').click();await page.evaluate(()=>resolveCamera());
  await page.waitForFunction(()=>stops===1);
  await open();
  await page.evaluate(async data=>{
    const img=new Image();img.src=data;await img.decode();
    const canvas=document.createElement('canvas');canvas.width=img.width;canvas.height=img.height;canvas.getContext('2d').drawImage(img,0,0);
    window.cameraCanvas=canvas;window.cameraStream=canvas.captureStream(10);
    Object.defineProperty(navigator.mediaDevices,'getUserMedia',{configurable:true,value:async()=>cameraStream});
  },'data:image/png;base64,'+fs.readFileSync('tests/fixtures/locator-pairing.png').toString('base64'));
  await page.locator('#camera').click();
  await page.waitForFunction(()=>document.querySelector('gwm-jolion-pairing').shadowRoot.querySelector('#key').value==='a'.repeat(48));
  assert.equal(await page.evaluate(()=>cameraStream.getTracks()[0].readyState),'ended');
  await page.locator('#close').click();
  await open();await page.locator('#key').fill('short');await page.locator('#save').click();assert.equal(await page.evaluate(()=>calls.length),0);
  fs.mkdirSync('dist',{recursive:true});await page.screenshot({path:'dist/pairing-preview.png'});
  assert.deepStrictEqual(errors,[]);console.log('QR photo, camera frame decoding, manual entry, invalid key, camera cleanup: PASS');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
