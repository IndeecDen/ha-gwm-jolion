// Compatibility alias: both saved card types use the same trips UI.
(async()=>{
  await customElements.whenDefined('gwm-jolion-trips-card');
  class LocatorCard extends customElements.get('gwm-jolion-trips-card') {}
  customElements.define('gwm-jolion-locator-card',LocatorCard);
})();
