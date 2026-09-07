// Run: node tests/remote_card_browser.cjs (requires Playwright).
// Optional GWM_BROWSER_CHANNEL=msedge and GWM_SCREENSHOTS=<output directory>.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const path = require('node:path');
(async () => {
  const browser = await chromium.launch({headless:true,channel:process.env.GWM_BROWSER_CHANNEL || undefined});
  try {
    const page = await browser.newPage({viewport:{width:900,height:900}});
    const errors=[];
    page.on('pageerror',e=>errors.push(e.message));
    await page.setContent('<style>body{background:#eef1f4;font-family:Arial;margin:24px}gwm-jolion-remote-card{display:block;width:400px}</style>');
    // HA supplies actual icons. Preview stand-ins use SVG and honor icon sizing.
    await page.evaluate(()=>customElements.define('ha-icon',class extends HTMLElement {
      static get observedAttributes(){return ['icon'];}
      constructor(){super();this.attachShadow({mode:'open'});}
      connectedCallback(){this.attributeChangedCallback();}
      attributeChangedCallback(){
        const paths={
          'mdi:lock':'M6 10h12v11H6z M8 10V6a4 4 0 018 0v4',
          'mdi:lock-open-variant':'M6 10h12v11H6z M8 10V6a4 4 0 018 0',
          'mdi:engine':'M5 8h12v11H5z M8 5h6 M11 5v3 M2 10v6 M2 13h3 M17 11h4v6h-4',
          'mdi:engine-off':'M5 8h12v11H5z M8 5h6 M2 2l20 20',
          'mdi:air-conditioner':'M12 2v20 M3 7l18 10 M3 17L21 7 M9 4l3 3 3-3 M9 20l3-3 3 3',
          'mdi:fan':'M12 12C0 0 22 0 12 12C24 0 24 22 12 12C24 24 0 24 12 12C0 24 0 0 12 12',
          'mdi:refresh':'M20 8A9 9 0 104 18 M20 2v6h-6',
          'mdi:car-back':'M4 11l2-6h12l2 6v8H4z M4 11h16 M6 15h3 M15 15h3',
          'mdi:fuel':'M4 22V3h10v19 M4 10h10 M14 7h3l3 3v8h-3v-6 M18 4l3 3',
          'mdi:counter':'M3 5h18v14H3z M7 9v6 M11 9h3v6h-3z M17 9v6',
          'mdi:car-door':'M4 20V9l5-6h11v17z M6 10h12 M14 14h3'
        };
        this.shadowRoot.innerHTML=`<style>:host{display:inline-flex;width:var(--mdc-icon-size,24px);height:var(--mdc-icon-size,24px)}svg{width:100%;height:100%}</style><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="${paths[this.getAttribute('icon')]||'M4 4h16v16H4z'}"/></svg>`;
      }
    }));
    for(const file of ['gwm-jolion-remote-card.js','gwm-jolion-alpha20.js'])await page.addScriptTag({path:path.resolve('custom_components/gwm_jolion/frontend',file)});
    await page.evaluate(()=>{
      window.calls=[];window.card=document.createElement('gwm-jolion-remote-card');
      card.setConfig({title:'Haval Jolion',confirm_controls:false});document.body.append(card);
      const values={engine:'off',doors:'off',doorFl:'off',doorFr:'off',doorRl:'off',doorRr:'off',windows:'off',trunk:'off',lock:'locked',climate:'off',tbox:'on',refresh:'unknown',fuel:'38',mileage:'24580'};
      card._entities=Object.fromEntries(Object.keys(values).map(k=>[k,`${k==='lock'?'lock':k==='climate'?'climate':k==='refresh'?'button':'sensor'}.${k}`]));card._resolvedKey='|';
      window.hass={states:Object.fromEntries(Object.entries(values).map(([k,state])=>[card._entities[k],{state,attributes:{unit_of_measurement:k==='fuel'?'л':k==='mileage'?'км':undefined}}])),themes:{darkMode:false},callService:async(...args)=>{calls.push(args);}};
      hass.states['sensor.tbox'].attributes.signal_level_raw=4;
      card.hass=hass;
    });
    const root=page.locator('gwm-jolion-remote-card');
    assert.equal(await root.locator('.security').getAttribute('opacity'),'1');
    assert.equal(await root.locator('.exhaust').getAttribute('opacity'),'0');
    for(const [action,expected] of [['lock',['lock','unlock',{entity_id:'lock.lock'}]],['engine',['gwm_jolion','start_engine',{operation_time:15}]],['climate',['climate','turn_on',{entity_id:'climate.climate'}]],['refresh',['button','press',{entity_id:'button.refresh'}]]]){
      await root.locator(`[data-action="${action}"]`).click();assert.deepEqual(await page.evaluate(()=>calls.pop()),expected);
    }
    await page.evaluate(()=>{window.originalCar=card.shadowRoot.querySelector('svg');hass.states['sensor.engine'].state='on';hass.states['sensor.doorFr'].state='on';hass.states['sensor.trunk'].state='on';card.hass=hass;});
    assert.equal(await page.evaluate(()=>originalCar===card.shadowRoot.querySelector('svg')),true);
    for(const cls of ['exhaust','door-indicator','trunk-indicator'])assert.equal(await root.locator('.'+cls).getAttribute('opacity'),'1');
    assert.match(await root.locator('[data-action="engine"]').innerText(),/Заглушить/);
    await root.locator('[data-action="engine"]').click();assert.deepEqual(await page.evaluate(()=>calls.pop()),['gwm_jolion','stop_engine',{}]);
    await page.evaluate(()=>{hass.states['lock.lock'].state='unavailable';card.hass=hass;});
    assert.equal(await root.locator('.security').getAttribute('opacity'),'0');
    assert.match(await root.locator('[data-status="lock"]').innerText(),/Нет данных/);
    await page.evaluate(()=>{card._busy.add('refresh');card._render();});
    assert.ok(await root.locator('.remote-action.busy').count());
    await page.evaluate(()=>{card._busy.clear();hass.states['lock.lock'].state='locked';card.hass=hass;});
    for(const dark of [false,true]){
      await page.evaluate(dark=>{hass.themes.darkMode=dark;card.hass=hass;},dark);
      assert.equal(await root.locator('ha-card').getAttribute('class'),dark?'dark':'light');
      for(const width of [280,400,700]){await page.evaluate(w=>card.style.width=w+'px',width);assert.equal(await root.evaluate(el=>el.shadowRoot.querySelector('ha-card').scrollWidth<=el.clientWidth),true,`overflow ${width}`);}
      await page.evaluate(()=>card.style.width='400px');
      assert.match(await root.locator('[data-action="engine"]').innerText(),/Заглушить/);
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      if(process.env.GWM_SCREENSHOTS)await root.screenshot({path:path.join(process.env.GWM_SCREENSHOTS,`remote-starline-${dark?'dark':'light'}.png`)});
    }
    await page.emulateMedia({reducedMotion:'reduce'});assert.equal(await root.locator('.smoke-1').evaluate(el=>getComputedStyle(el).animationName),'none');
    assert.deepEqual(errors,[]);console.log('Passed: commands, alpha.20 states, labels, retained DOM, themes, 280/400/700px layouts, reduced motion.');
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
