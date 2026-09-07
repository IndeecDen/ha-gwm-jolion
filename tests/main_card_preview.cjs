// Run: node tests/remote_card_browser.cjs (requires Playwright).
// Optional GWM_BROWSER_CHANNEL=msedge and GWM_SCREENSHOTS=<output directory>.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const path = require('node:path');
(async () => {
  const browser = await chromium.launch({headless:true,channel:process.env.GWM_BROWSER_CHANNEL || undefined});
  try {
    const page = await browser.newPage({viewport:{width:560,height:1100}});
    const errors=[];
    page.on('pageerror',e=>errors.push(e.message));
    await page.setContent('<style>body{background:#eef1f4;font-family:Arial;margin:20px;--primary-text-color:#17283b;--secondary-text-color:#677b90;--primary-color:#237ada;--card-background-color:#fff;--divider-color:#dce4ed;--disabled-text-color:#8794a2}gwm-jolion-card{display:block;width:520px}</style>');
    // HA supplies actual icons. Preview stand-ins use SVG and honor icon sizing.
    await page.evaluate(()=>customElements.define('ha-icon',class extends HTMLElement {
      static get observedAttributes(){return ['icon'];}
      constructor(){super();this.attachShadow({mode:'open'});}
      connectedCallback(){this.attributeChangedCallback();}
      attributeChangedCallback(){
        const paths={
          'mdi:timer-outline':'M9 2h6 M12 2v3 M8 6a8 8 0 1010 2 M12 8v5l3 2',
          'mdi:car-seat-heater':'M6 3v10h10v7 M5 16h8 M15 3q-2 2 0 4t0 4 M19 3q-2 2 0 4t0 4',
          'mdi:steering':'M12 3a9 9 0 100 18 9 9 0 000-18 M3 11h18 M12 11v10',
          'mdi:car-defrost-rear':'M3 18V6h18v12H3 M7 15V8 M12 15V8 M17 15V8',
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

 for(const file of ['gwm-jolion-card.js','gwm-jolion-alpha20.js'])await page.addScriptTag({path:path.resolve('custom_components/gwm_jolion/frontend',file)});
 await page.evaluate(()=>{
 const card=document.createElement('gwm-jolion-card');document.body.append(card);card.setConfig({title:'Haval Jolion'});card._entryId='demo';card._resolvedKey='|';
 const values={engine:'off',doors:'off',windows:'off',windowFl:'off',windowFr:'off',windowRl:'off',windowRr:'off',trunk:'off',climateOn:'on',climate:'heat_cool',climateRuntime:'15',lock:'locked',tbox:'on',fuel:'38',fuelPercent:'69',range:'450',mileage:'24580',seatDriver:'3',seatPassenger:'1',tireFlP:'2.3',tireFrP:'2.3',tireRlP:'2.2',tireRrP:'2.2',tireFlT:'21',tireFrT:'22',tireRlT:'20',tireRrT:'21',refresh:'unknown'};
 card._entities=Object.fromEntries(Object.keys(values).map(k=>[k,'sensor.'+k]));
 const states=Object.fromEntries(Object.entries(values).map(([key,state])=>[card._entities[key],{state,attributes:{}}]));
 states['sensor.climate'].attributes={temperature:23};states['sensor.tbox'].attributes={signal_level_raw:4,feature_flags:{steering_wheel_heat:true,rear_defrost:true,seat_heat_driver:true,seat_heat_passenger:true}};
 states['sensor.refresh'].attributes={last_successful_update:new Date().toISOString()};
 card._seatSettings={driver:3,passenger:1,operation_time:5};card._hass={states,callService:async()=>{}};card._render();
 });
 await page.evaluate(()=>{const c=document.querySelector('gwm-jolion-card');c.shadowRoot.querySelector('ha-card').style.display='block';});
 await page.locator('gwm-jolion-card').screenshot({path:'docs/gwm-jolion-card.png'});
 assert.deepEqual(errors,[]);
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
