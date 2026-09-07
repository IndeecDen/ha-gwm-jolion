/* GWM Jolion Remote Card v0.1.0-alpha.19.4 */
(() => {
const CARD_VERSION = "0.1.0-alpha.19.4";
const INTEGRATION = "gwm_jolion";
const DEFAULT_CONTROLS = ["lock", "engine", "climate"];
const DEFAULT_INFO = [];
const DEFAULT_STATUSES = ["engine", "climate", "fuel", "mileage", "doors", "windows", "trunk", "lock"];
const CONTROL_OPTIONS = [
["lock", "Центральный замок"],
["engine", "Двигатель"],
["climate", "Климат"],
["trunk", "Багажник"],
["windows", "Окна"],
["refresh", "Обновление данных"],
["steering", "Обогрев руля"],
["rear_defrost", "Обогрев заднего стекла"],
["front_defrost", "Передний defrost"],
["sunroof", "Панорамная крыша / люк"],
["sunshade", "Шторка панорамной крыши"],
];
const INFO_OPTIONS = [
["fuel", "Топливо"],
["range", "Запас хода"],
["mileage", "Пробег"],
["tires", "Давление шин"],
["gsm", "GSM / T-Box"],
["gps", "GPS"],
["climate", "Климат"],
["oil", "Уровень масла GWM"],
["update", "Последнее обновление"],
];
const STATUS_OPTIONS = [
["engine", "Двигатель"],
["climate", "Климат"],
["fuel", "Топливо"],
["mileage", "Пробег"],
["doors", "Двери"],
["windows", "Окна"],
["trunk", "Багажник"],
["lock", "Замок"],
];
const SUFFIX = {
engine: "_engine_running",
doors: "_doors_open",
doorFl: "_door_front_left_open",
doorFr: "_door_front_right_open",
doorRl: "_door_rear_left_open",
doorRr: "_door_rear_right_open",
windows: "_windows_open",
window1: "_window_2210001_open",
window1Raw: "_window_2210001_raw",
trunk: "_trunk_open",
unlocked: "_vehicle_unlocked",
climateOn: "_climate_on",
tbox: "_tbox_online",
gps: "_gps_authorized",
lock: "_central_lock",
climate: "_climate",
refresh: "_refresh",
fuel: "_fuel_liters",
fuelPercent: "_fuel_percent",
range: "_range_km",
mileage: "_mileage_total",
modelCode: "_model_code_raw",
oilQty: "_oil_qty",
lastUpdate: "_last_successful_update",
tireFlP: "_tire_fl_pressure",
tireFrP: "_tire_fr_pressure",
tireRlP: "_tire_rl_pressure",
tireRrP: "_tire_rr_pressure",
signal: "_tbox_signal_raw",
lastCommand: "_last_command",
featureFlags: "_feature_flags",
steeringHeat: "_steering_wheel_heat_on",
rearDefrost: "_rear_defrost_on",
frontDefrost: "_front_defrost_on",
light7Raw: "_light_2204007_raw",
light8Raw: "_light_2204008_raw",
};
const FEATURE_BY_CONTROL = {
steering: "steering_wheel_heat",
rear_defrost: "rear_defrost",
front_defrost: "front_defrost",
sunroof: "sunroof",
sunshade: "sunshade",
};
class GwmJolionRemoteCardEditor extends HTMLElement {
constructor() {
super();
this.attachShadow({ mode: "open" });
this._config = {};
}
set hass(hass) {
this._hass = hass;
}
setConfig(config) {
this._config = {
controls: [...DEFAULT_CONTROLS],
info: [...DEFAULT_INFO],
statuses: [...DEFAULT_STATUSES],
confirm_controls: true,
car_color: "#74808b",
...config,
};
this._render();
}
_escape(value) {
return String(value ?? "")
.replaceAll("&", "&amp;")
.replaceAll("<", "&lt;")
.replaceAll(">", "&gt;")
.replaceAll('"', "&quot;")
.replaceAll("'", "&#039;");
}
_emit(config) {
this._config = config;
this.dispatchEvent(
new CustomEvent("config-changed", {
detail: { config },
bubbles: true,
composed: true,
}),
);
this._render();
}
_group(title, key, options) {
const selected = Array.isArray(this._config[key]) ? this._config[key] : [];
return `
<section>
<h4>${title}</h4>
<div class="grid">
${options
.map(
([value, label]) => `
<label>
<input
 type="checkbox"
 data-list="${key}"
 data-value="${value}"
 ${selected.includes(value) ? "checked" : ""}
>
<span>${label}</span>
</label>
`,
)
.join("")}
</div>
</section>
`;
}
_render() {
if (!this.shadowRoot) return;
const color = /^#[0-9a-f]{6}$/i.test(this._config.car_color || "")
? this._config.car_color
: "#74808b";
this.shadowRoot.innerHTML = `
<style>
:host{display:block}
.editor{display:grid;gap:15px;padding:4px 0 12px}
section{display:grid;gap:7px}
h4{margin:0;font-size:14px}
.row{display:grid;grid-template-columns:1fr auto;gap:12px;align-items:end}
.field{display:grid;gap:6px;font-size:12px;color:var(--secondary-text-color)}
input[type=text]{min-height:40px;border:1px solid var(--divider-color);border-radius:8px;background:var(--card-background-color);color:var(--primary-text-color);padding:0 10px}
.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px 14px}
.grid label,.check{display:flex;align-items:center;gap:8px;min-height:30px;font-size:13px}
.note{padding:10px 12px;border-radius:10px;background:color-mix(in srgb,var(--primary-color) 7%,transparent);font-size:12px;color:var(--secondary-text-color);line-height:1.45}
@media(max-width:520px){.grid{grid-template-columns:1fr}}
</style>
<div class="editor">
<div class="row">
<label class="field">
Название
<input id="title" type="text" value="${this._escape(this._config.title || "")}" placeholder="Haval Jolion">
</label>
<label class="field">
Цвет
<input id="color" type="color" value="${color}">
</label>
</div>
<label class="check">
<input id="confirm" type="checkbox" ${this._config.confirm_controls !== false ? "checked" : ""}>
Подтверждать удалённые команды
</label>
${this._group("Кнопки управления", "controls", CONTROL_OPTIONS)}
${this._group("Дополнительная информация", "info", INFO_OPTIONS)}
${this._group("Нижние статусы", "statuses", STATUS_OPTIONS)}
<div class="note">
Новый горизонтальный вид сверху: капот слева, багажник справа.
Верхняя сторона SVG — левая сторона автомобиля, нижняя — правая.
Все четыре двери имеют ось петель на своей левой кромке по направлению автомобиля.
Фары подготовлены отдельным слоем, но не привязаны к неподтверждённым telemetry-кодам.
</div>
</div>
`;
this.shadowRoot.querySelectorAll("[data-list]").forEach((element) => {
element.addEventListener("change", () => {
const key = element.dataset.list;
const value = element.dataset.value;
const current = [...(this._config[key] || [])];
this._emit({
...this._config,
[key]: element.checked
? current.includes(value)
? current
: [...current, value]
: current.filter((item) => item !== value),
});
});
});
this.shadowRoot.getElementById("confirm")?.addEventListener("change", (event) => {
this._emit({ ...this._config, confirm_controls: event.target.checked });
});
this.shadowRoot.getElementById("title")?.addEventListener("change", (event) => {
const next = { ...this._config };
const value = String(event.target.value || "").trim();
if (value) next.title = value;
else delete next.title;
this._emit(next);
});
this.shadowRoot.getElementById("color")?.addEventListener("change", (event) => {
this._emit({ ...this._config, car_color: event.target.value });
});
}
}
class GwmJolionRemoteCard extends HTMLElement {
constructor() {
super();
this.attachShadow({ mode: "open" });
this._config = {};
this._hass = null;
this._entities = {};
this._device = null;
this._resolving = false;
this._resolvedKey = null;
this._busy = new Set();
this._assumed = {};
}
static getStubConfig() {
return {
controls: [...DEFAULT_CONTROLS],
info: [...DEFAULT_INFO],
statuses: [...DEFAULT_STATUSES],
};
}
static getConfigElement() {
return document.createElement("gwm-jolion-remote-card-editor");
}
static getGridOptions() {
return { columns: 12, rows: 11, min_columns: 6, min_rows: 7 };
}
setConfig(config) {
this._config = {
controls: [...DEFAULT_CONTROLS],
info: [...DEFAULT_INFO],
statuses: [...DEFAULT_STATUSES],
confirm_controls: true,
car_color: "#74808b",
...config,
};
this._resolvedKey = null;
if (this._hass) this._resolveEntities();
this._render();
}
set hass(hass) {
this._hass = hass;
const key = `${this._config.device_id || ""}|${this._config.entity || ""}`;
if (this._resolvedKey !== key && !this._resolving) this._resolveEntities();
this._render();
}
getCardSize() {
return 11;
}
async _resolveEntities() {
if (!this._hass || this._resolving) return;
this._resolving = true;
try {
const registry = await this._hass.callWS({ type: "config/entity_registry/list" });
let deviceId = this._config.device_id || null;
if (!deviceId && this._config.entity) {
deviceId = registry.find((entry) => entry.entity_id === this._config.entity)?.device_id || null;
}
const gwmEntries = registry.filter(
(entry) => entry.platform === INTEGRATION || this._isGwmUniqueId(entry.unique_id),
);
if (!deviceId) deviceId = gwmEntries.find((entry) => entry.device_id)?.device_id || null;
const entries = deviceId
? gwmEntries.filter((entry) => entry.device_id === deviceId)
: gwmEntries;
const devices = await this._hass.callWS({ type: "config/device_registry/list" });
this._device = devices.find((device) => device.id === deviceId) || null;
this._entities = {};
for (const [key, suffix] of Object.entries(SUFFIX)) {
const found = entries.find((entry) => String(entry.unique_id || "").endsWith(suffix));
if (found) this._entities[key] = found.entity_id;
}
this._entities.climate ||= entries.find((entry) => entry.entity_id.startsWith("climate."))?.entity_id;
this._entities.lock ||= entries.find((entry) => entry.entity_id.startsWith("lock."))?.entity_id;
this._entities.refresh ||= entries.find(
(entry) => entry.entity_id.startsWith("button.") && /refresh|obnov/i.test(entry.entity_id),
)?.entity_id;
this._resolvedKey = `${this._config.device_id || ""}|${this._config.entity || ""}`;
} catch (error) {
console.error("[GWM Jolion Remote Card] entity discovery failed", error);
} finally {
this._resolving = false;
this._render();
}
}
_isGwmUniqueId(uniqueId) {
return uniqueId && Object.values(SUFFIX).some((suffix) => String(uniqueId).endsWith(suffix));
}
_state(key) {
const entityId = this._entities[key];
return entityId ? this._hass?.states?.[entityId] : undefined;
}
_isOn(key) {
return this._state(key)?.state === "on";
}
_isUnavailable(key) {
const state = this._state(key)?.state;
return !state || state === "unknown" || state === "unavailable";
}
_raw(key) {
const state = this._state(key)?.state;
return !state || ["unknown", "unavailable"].includes(state) ? null : String(state);
}
_value(key, fallback = "—") {
const state = this._state(key);
if (!state || ["unknown", "unavailable", ""].includes(state.state)) return fallback;
const unit = state.attributes?.unit_of_measurement;
return `${state.state}${unit ? ` ${unit}` : ""}`;
}
_icon(icon) {
return `<ha-icon icon="${icon}"></ha-icon>`;
}
_escape(value) {
return String(value ?? "")
.replaceAll("&", "&amp;")
.replaceAll("<", "&lt;")
.replaceAll(">", "&gt;")
.replaceAll('"', "&quot;")
.replaceAll("'", "&#039;");
}
_safeColor() {
return /^#[0-9a-f]{6}$/i.test(this._config.car_color || "")
? this._config.car_color
: "#74808b";
}
_featureEnabled(key) {
const flags = this._state("featureFlags");
return !flags?.attributes || !(key in flags.attributes) || flags.attributes[key] !== false;
}
_remoteBusy() {
return this._state("lastCommand")?.attributes?.in_progress === true;
}
_drivetrain() {
const raw = (this._raw("modelCode") || "").toUpperCase();
if (raw.includes("CC7150BA24C")) return "4WD";
if (raw.includes("CC7150BA00B") || raw.includes("CC7150BA01B")) return "2WD";
return null;
}
_title() {
if (this._config.title) return String(this._config.title);
const model = String(this._device?.model || "Haval Jolion").trim();
const drivetrain = this._drivetrain();
return drivetrain ? `${model} ${drivetrain}` : model;
}
_relativeUpdate() {
const raw = this._raw("lastUpdate");
if (!raw) return "нет данных";
const time = new Date(raw).getTime();
if (!Number.isFinite(time)) return "нет данных";
const seconds = Math.max(0, Math.round((Date.now() - time) / 1000));
if (seconds < 60) return `${seconds} сек назад`;
const minutes = Math.floor(seconds / 60);
if (minutes < 60) return `${minutes} мин назад`;
const hours = Math.floor(minutes / 60);
return hours < 24 ? `${hours} ч назад` : `${Math.floor(hours / 24)} дн назад`;
}
_climateOn() {
const climate = this._state("climate");
return (
this._isOn("climateOn") ||
["heat_cool", "heat", "cool", "fan_only"].includes(climate?.state)
);
}
_windowLevel(raw) {
const value = Number(raw);
if (value === 1) return 0;
if (value === 3) return 0.52;
if (value === 2) return 1;
return null;
}
_doorState(key) {
return !this._isUnavailable(key) && this._isOn(key);
}
_doorStates() {
return {
fl: this._doorState("doorFl"),
fr: this._doorState("doorFr"),
rl: this._doorState("doorRl"),
rr: this._doorState("doorRr"),
};
}
_doorCount() {
const keys = ["doorFl", "doorFr", "doorRl", "doorRr"];
const available = keys.filter((key) => !this._isUnavailable(key));
if (!available.length) return null;
return available.filter((key) => this._isOn(key)).length;
}
_signalBars() {
const raw = Number(this._raw("signal"));
const known = Number.isFinite(raw);
return `
<span class="signal-bars" aria-label="GSM ${known ? `${raw} из 4` : "нет данных"}">
${[1, 2, 3, 4]
.map(
(index) => `
<i
 class="${known && index <= raw ? "on" : ""}"
 style="height:${5 + index * 4}px"
></i>
`,
)
.join("")}
</span>
`;
}
_doorLabel(kind, open) {
const labels = {
fl: ["Передняя левая", 400, 48],
rl: ["Задняя левая", 700, 48],
fr: ["Передняя правая", 400, 486],
rr: ["Задняя правая", 700, 486],
};
const [title, x, y] = labels[kind];
return `
<g class="door-state-label ${open ? "is-open" : ""}">
<text class="door-label-title" x="${x}" y="${y}">${title}</text>
<text class="door-label-state" x="${x}" y="${y + 22}">${open ? "Открыта" : "Закрыта"}</text>
</g>
`;
}
_carSvg() {
const engine = this._isOn("engine");
const climate = this._climateOn();
const trunk = this._isOn("trunk");
const unlocked = !this._isUnavailable("unlocked") && this._isOn("unlocked");
const lockClass = this._isUnavailable("unlocked") ? "lock-unknown" : unlocked ? "lock-open" : "lock-closed";
const doors = this._doorStates();
const aggregateDoors = this._isOn("doors");
const specificKnown = ["doorFl", "doorFr", "doorRl", "doorRr"].some(
(key) => !this._isUnavailable(key),
);
const unknownDoorOpen = aggregateDoors && !specificKnown;
const anyWindows = this._isOn("windows");
const flWindowLevelRaw = this._windowLevel(this._raw("window1Raw"));
const flWindowLevel = flWindowLevelRaw === null
? this._isUnavailable("window1")
? null
: this._isOn("window1")
? 1
: 0
: flWindowLevelRaw;
const flGlassOpacity = flWindowLevel === null ? 0.88 : Math.max(0.08, 0.92 - flWindowLevel * 0.82);
const flGlassScale = flWindowLevel === null ? 1 : Math.max(0.25, 1 - flWindowLevel * 0.72);
return `
<svg
 class="jolion-scene ${lockClass} ${engine ? "engine-on" : ""} ${climate ? "climate-on" : ""} ${trunk ? "trunk-open" : ""} ${anyWindows ? "windows-open" : ""} ${unknownDoorOpen ? "unknown-door-open" : ""}"
 viewBox="0 0 1200 520"
 role="img"
 aria-label="Haval Jolion вид сверху. Капот слева, багажник справа, левая сторона автомобиля сверху."
>
<defs>
<linearGradient id="bodyPaint" x1="0" x2="1" y1="0" y2="1">
<stop offset="0" stop-color="color-mix(in srgb,var(--gwm-car-color) 50%,white 50%)"/>
<stop offset=".18" stop-color="color-mix(in srgb,var(--gwm-car-color) 80%,white 20%)"/>
<stop offset=".56" stop-color="var(--gwm-car-color)"/>
<stop offset="1" stop-color="color-mix(in srgb,var(--gwm-car-color) 62%,black 38%)"/>
</linearGradient>
<linearGradient id="bodyDark" x1="0" x2="1">
<stop offset="0" stop-color="color-mix(in srgb,var(--gwm-car-color) 84%,black 16%)"/>
<stop offset="1" stop-color="color-mix(in srgb,var(--gwm-car-color) 58%,black 42%)"/>
</linearGradient>
<linearGradient id="glass" x1="0" y1="0" x2="1" y2="1">
<stop offset="0" stop-color="#233746"/>
<stop offset=".45" stop-color="#0c1720"/>
<stop offset="1" stop-color="#071018"/>
</linearGradient>
<linearGradient id="doorGlass" x1="0" x2="1">
<stop offset="0" stop-color="#173149"/>
<stop offset=".55" stop-color="#0d2232"/>
<stop offset="1" stop-color="#06111a"/>
</linearGradient>
<filter id="shadow" x="-30%" y="-30%" width="160%" height="160%">
<feDropShadow dx="0" dy="12" stdDeviation="18" flood-color="#000" flood-opacity=".5"/>
</filter>
<filter id="blueGlow" x="-80%" y="-80%" width="260%" height="260%">
<feGaussianBlur stdDeviation="9" result="blur"/>
<feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
</filter>
<filter id="orangeGlow" x="-80%" y="-80%" width="260%" height="260%">
<feGaussianBlur stdDeviation="11" result="blur"/>
<feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
</filter>
<filter id="redGlow" x="-80%" y="-80%" width="260%" height="260%">
<feGaussianBlur stdDeviation="8" result="blur"/>
<feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
</filter>
</defs>
<ellipse class="vehicle-aura" cx="600" cy="260" rx="420" ry="168"/>
<g class="vehicle" filter="url(#shadow)">
<path
 class="car-body"
 d="M155 260
 C168 174 226 130 322 111
 C463 83 722 83 894 112
 C978 126 1034 178 1051 260
 C1034 342 978 394 894 408
 C722 437 463 437 322 409
 C226 390 168 346 155 260 Z"
/>
<path
 class="hood-panel"
 d="M177 260
 C185 196 229 154 310 137
 L384 121
 C405 159 412 203 412 260
 C412 317 405 361 384 399
 L310 383
 C229 366 185 324 177 260 Z"
/>
<path class="hood-center" d="M213 260 C226 204 264 173 330 157 L367 149 M213 260 C226 316 264 347 330 363 L367 371"/>
<path
 class="roof-frame"
 d="M405 129
 C497 101 713 101 829 127
 L887 170
 L887 350
 L829 393
 C713 419 497 419 405 391
 L372 337
 L372 183 Z"
/>
<path class="front-windshield glass" d="M405 145 C453 125 491 117 532 113 L532 407 C491 403 453 395 405 375 L385 332 L385 188 Z"/>
<path class="rear-windshield glass" d="M790 116 C832 122 860 137 884 166 L884 354 C860 383 832 398 790 404 Z"/>
<rect class="cabin-glass glass" x="538" y="113" width="246" height="294" rx="32"/>
<g class="cabin-seats">
<rect x="567" y="145" width="72" height="91" rx="26"/>
<rect x="567" y="284" width="72" height="91" rx="26"/>
<rect x="677" y="145" width="72" height="91" rx="26"/>
<rect x="677" y="284" width="72" height="91" rx="26"/>
<line x1="657" y1="126" x2="657" y2="394"/>
</g>
<g class="engine-visual">
<ellipse class="engine-halo" cx="292" cy="260" rx="74" ry="91"/>
<path class="engine-icon" d="M257 235 h63 v51 h-63 z M269 224 h39 v11 M249 246 h8 M320 246 h11 v29 h-11 M273 286 v12 h32 v-12"/>
</g>
<g class="climate-visual">
<circle class="fan-ring" cx="657" cy="260" r="24"/>
<circle class="fan-core" cx="657" cy="260" r="7"/>
<g class="fan-blades">
<path class="fan-blade" d="M657 252 C639 239 637 225 649 221 C662 218 665 237 657 252Z"/>
<path class="fan-blade" d="M665 260 C678 242 692 240 696 252 C700 265 680 268 665 260Z"/>
<path class="fan-blade" d="M657 268 C675 281 677 295 665 299 C652 302 649 283 657 268Z"/>
<path class="fan-blade" d="M649 260 C636 278 622 280 618 268 C614 255 634 252 649 260Z"/>
</g>
<path class="airflow airflow-a" d="M632 247 C603 220 584 195 567 164"/>
<path class="airflow airflow-b" d="M632 273 C603 300 584 325 567 356"/>
<path class="airflow airflow-c" d="M682 247 C711 220 730 195 747 164"/>
<path class="airflow airflow-d" d="M682 273 C711 300 730 325 747 356"/>
</g>
<g class="headlights">
<path class="headlamp" d="M174 194 C189 169 213 153 246 144 L262 157 L211 190 Z"/>
<path class="headlamp" d="M174 326 C189 351 213 367 246 376 L262 363 L211 330 Z"/>
<path class="headlight-beam" d="M170 190 L58 135 L80 222 Z"/>
<path class="headlight-beam" d="M170 330 L58 385 L80 298 Z"/>
</g>
<g class="rear-lights">
<path class="tail-light" d="M1000 165 C1022 181 1038 201 1046 224 L1024 229 L988 193 Z"/>
<path class="tail-light" d="M1000 355 C1022 339 1038 319 1046 296 L1024 291 L988 327 Z"/>
</g>
<!--
 Door geometry contract:
 top side = left side of the vehicle;
 bottom side = right side of the vehicle;
 all four doors hinge on the LEFT edge of their own panel (frontward edge).
-->
<g class="door door-fl left-side ${doors.fl ? "open" : ""}">
<path class="door-panel" d="M402 135 L568 108 L568 169 L402 184 Z"/>
<path
 class="door-window"
 d="M425 142 L553 121 L553 158 L425 170 Z"
 style="opacity:${flGlassOpacity.toFixed(2)};transform:scaleY(${flGlassScale.toFixed(2)})"
/>
</g>
<circle class="hinge hinge-fl" cx="402" cy="160" r="4"/>
<g class="door door-rl left-side ${doors.rl ? "open" : ""}">
<path class="door-panel" d="M579 107 L785 116 L785 171 L579 168 Z"/>
<path class="door-window generic-window" d="M595 119 L767 127 L767 158 L595 157 Z"/>
</g>
<circle class="hinge hinge-rl" cx="579" cy="138" r="4"/>
<g class="door door-fr right-side ${doors.fr ? "open" : ""}">
<path class="door-panel" d="M402 385 L568 412 L568 351 L402 336 Z"/>
<path class="door-window generic-window" d="M425 378 L553 399 L553 362 L425 350 Z"/>
</g>
<circle class="hinge hinge-fr" cx="402" cy="360" r="4"/>
<g class="door door-rr right-side ${doors.rr ? "open" : ""}">
<path class="door-panel" d="M579 413 L785 404 L785 349 L579 352 Z"/>
<path class="door-window generic-window" d="M595 401 L767 393 L767 362 L595 363 Z"/>
</g>
<circle class="hinge hinge-rr" cx="579" cy="382" r="4"/>
<g class="trunk-lid">
<path
 class="trunk-panel"
 d="M891 170
 C946 181 987 209 1008 260
 C987 311 946 339 891 350
 Z"
/>
<path class="rear-glass glass" d="M903 189 C941 202 967 224 981 260 C967 296 941 318 903 331 Z"/>
</g>
<path class="front-bumper" d="M160 219 C146 236 144 284 160 301"/>
<path class="rear-bumper" d="M1048 219 C1062 236 1064 284 1048 301"/>
</g>
${this._doorLabel("fl", doors.fl)}
${this._doorLabel("rl", doors.rl)}
${this._doorLabel("fr", doors.fr)}
${this._doorLabel("rr", doors.rr)}
<g class="trunk-state-label ${trunk ? "is-open" : ""}">
<text x="1085" y="252">Багажник</text>
<text class="state" x="1085" y="276">${trunk ? "Открыт" : "Закрыт"}</text>
</g>
</svg>
`;
}
_doorSummary() {
const count = this._doorCount();
if (count === null) {
if (this._isUnavailable("doors")) return "—";
return this._isOn("doors") ? "Есть открытые" : "Закрыты";
}
return count === 0 ? "Закрыты" : `${count} ${count === 1 ? "открыта" : "открыты"}`;
}
_statusMeta(id) {
const engine = this._isOn("engine");
const climate = this._climateOn();
const windows = this._isOn("windows");
const trunk = this._isOn("trunk");
const unlocked = this._isOn("unlocked");
const unknown = (key) => this._isUnavailable(key);
return {
engine: [
"mdi:engine",
"Двигатель",
unknown("engine") ? "—" : engine ? "Работает" : "Выключен",
engine ? "engine" : "ok",
],
climate: [
"mdi:fan",
"Климат",
!this._state("climate") && unknown("climateOn") ? "—" : climate ? "Включён" : "Выключен",
climate ? "climate" : "ok",
],
fuel: ["mdi:fuel", "Топливо", this._value("fuel"), "info"],
mileage: ["mdi:counter", "Пробег", this._value("mileage"), "info"],
doors: [
"mdi:car-door",
"Двери",
this._doorSummary(),
this._isOn("doors") ? "warn" : "ok",
],
windows: [
"mdi:car-door",
"Окна",
unknown("windows") ? "—" : windows ? "Открыты" : "Закрыты",
windows ? "warn" : "ok",
],
trunk: [
"mdi:car-back",
"Багажник",
unknown("trunk") ? "—" : trunk ? "Открыт" : "Закрыт",
trunk ? "warn" : "ok",
],
lock: [
unlocked ? "mdi:lock-open-variant" : "mdi:lock",
"Замок",
unknown("unlocked") ? "—" : unlocked ? "Разблокирован" : "Закрыт",
unlocked ? "unlock" : "lock",
],
}[id] || null;
}
_renderStatuses() {
const selected = Array.isArray(this._config.statuses)
? this._config.statuses
: DEFAULT_STATUSES;
return `
<div class="status-dock">
${selected
.map((id) => {
const meta = this._statusMeta(id);
if (!meta) return "";
return `
<div class="status-tile ${meta[3]}">
<span class="status-icon">${this._icon(meta[0])}</span>
<span class="status-copy">
<small>${this._escape(meta[1])}</small>
<strong>${this._escape(meta[2])}</strong>
</span>
</div>
`;
})
.join("")}
</div>
`;
}
_infoMeta(id) {
const pressures = ["tireFlP", "tireFrP", "tireRlP", "tireRrP"]
.map((key) => this._raw(key))
.filter(Boolean);
return {
fuel: ["mdi:fuel", "Топливо", this._value("fuel")],
range: ["mdi:map-marker-distance", "Запас хода", this._value("range")],
mileage: ["mdi:counter", "Пробег", this._value("mileage")],
tires: [
"mdi:car-tire-alert",
"Шины",
pressures.length ? `${pressures.join(" / ")} bar` : "—",
],
gsm: ["mdi:signal", "GSM", `${this._raw("signal") ?? "—"}/4`],
gps: [
"mdi:crosshairs-gps",
"GPS",
this._isUnavailable("gps") ? "—" : this._isOn("gps") ? "есть" : "нет",
],
climate: [
"mdi:air-conditioner",
"Климат",
this._climateOn() ? "работает" : "выключен",
],
oil: [
"mdi:oil",
"Масло",
this._raw("oilQty") === null ? "—" : `${this._raw("oilQty")}/8`,
],
update: ["mdi:cloud-sync", "Обновление", this._relativeUpdate()],
}[id] || null;
}
_renderInfo() {
const selected = Array.isArray(this._config.info) ? this._config.info : DEFAULT_INFO;
const items = selected.map((id) => this._infoMeta(id)).filter(Boolean);
if (!items.length) return "";
return `
<div class="info-grid">
${items
.map(
(meta) => `
<div class="info-tile">
${this._icon(meta[0])}
<div>
<small>${this._escape(meta[1])}</small>
<strong>${this._escape(meta[2])}</strong>
</div>
</div>
`,
)
.join("")}
</div>
`;
}
_controlMeta(id) {
const feature = FEATURE_BY_CONTROL[id];
if (feature && !this._featureEnabled(feature)) return null;
const unlocked = this._isOn("unlocked");
const engine = this._isOn("engine");
const climate = this._climateOn();
const trunk = this._isOn("trunk");
const windows = this._isOn("windows");
const steering = !this._isUnavailable("steeringHeat")
? this._isOn("steeringHeat")
: Boolean(this._assumed.steeringHeat);
const rear = !this._isUnavailable("rearDefrost")
? this._isOn("rearDefrost")
: Boolean(this._assumed.rearDefrost);
const front = !this._isUnavailable("frontDefrost")
? this._isOn("frontDefrost")
: Boolean(this._assumed.frontDefrost);
return {
lock: [
unlocked ? "mdi:lock" : "mdi:lock-open-variant",
unlocked ? "Закрыть" : "Открыть",
unlocked ? "active" : "",
this._isUnavailable("unlocked"),
],
engine: [
engine ? "mdi:engine-off" : "mdi:engine",
engine ? "Заглушить" : "Запустить",
engine ? "active" : "",
this._isUnavailable("engine"),
],
climate: [
"mdi:air-conditioner",
climate ? "Климат выкл." : "Климат вкл.",
climate ? "active" : "",
false,
],
trunk: [
"mdi:car-back",
trunk ? "Закрыть багажник" : "Открыть багажник",
trunk ? "warn" : "",
this._isUnavailable("trunk"),
],
windows: [
"mdi:car-door",
windows ? "Закрыть окна" : "Открыть окна",
windows ? "warn" : "",
this._isUnavailable("windows"),
],
refresh: ["mdi:refresh", "Обновить", "", false],
steering: [
"mdi:steering",
steering ? "Руль выкл." : "Руль вкл.",
steering ? "active" : "",
false,
],
rear_defrost: [
"mdi:car-defrost-rear",
rear ? "Заднее выкл." : "Заднее вкл.",
rear ? "active" : "",
false,
],
front_defrost: [
"mdi:car-defrost-front",
front ? "Defrost выкл." : "Defrost вкл.",
front ? "active" : "experimental",
false,
],
sunroof: ["mdi:car-select", "Панорама", "experimental", false],
sunshade: ["mdi:blinds", "Шторка", "experimental", false],
}[id] || null;
}
_renderControls() {
const selected = Array.isArray(this._config.controls)
? this._config.controls
: DEFAULT_CONTROLS;
const remoteBusy = this._remoteBusy();
const items = selected
.map((id) => {
const meta = this._controlMeta(id);
if (!meta) return "";
const busy = this._busy.has(id) || (remoteBusy && id !== "refresh");
const disabled = meta[3] || busy;
return `
<button
 class="remote-action ${meta[2]} ${busy ? "busy" : ""}"
 ${disabled ? "disabled" : `data-action="${id}"`}
>
<span class="action-circle">${this._icon(meta[0])}</span>
<span>${this._escape(meta[1])}</span>
</button>
`;
})
.join("");
return items ? `<div class="remote-controls">${items}</div>` : "";
}
_render() {
if (!this.shadowRoot) return;
if (!this._hass) {
this.shadowRoot.innerHTML = `<ha-card><div style="padding:20px">GWM Jolion Remote Card</div></ha-card>`;
return;
}
const onlineKnown = !this._isUnavailable("tbox");
const online = onlineKnown && this._isOn("tbox");
const unlockedKnown = !this._isUnavailable("unlocked");
const unlocked = unlockedKnown && this._isOn("unlocked");
const lockTone = !unlockedKnown ? "unknown" : unlocked ? "unlocked" : "locked";
this.shadowRoot.innerHTML = `
<style>
:host{
display:block;
--gwm-car-color:${this._safeColor()};
--gwm-bg:#101922;
--gwm-panel:#15212c;
--gwm-panel-2:#0d161f;
--gwm-line:rgba(255,255,255,.12);
--gwm-muted:#93a0ab;
--gwm-text:#f0f4f7;
--gwm-blue:#36a9ff;
--gwm-orange:#ff9b22;
--gwm-red:#ff4141;
--gwm-green:#18ca6a;
--gwm-yellow:#ffc338;
}
*{box-sizing:border-box}
ha-card{
overflow:hidden;
border-radius:var(--ha-card-border-radius,22px);
background:
radial-gradient(circle at 50% -20%,rgba(64,107,139,.20),transparent 45%),
linear-gradient(180deg,#111c26 0%,#0b131b 100%);
color:var(--gwm-text);
border:1px solid rgba(255,255,255,.07);
}
.wrap{padding:12px}
.stage{
position:relative;
min-height:430px;
overflow:hidden;
border-radius:20px;
background:
radial-gradient(circle at 49% 52%,rgba(75,108,132,.16),transparent 48%),
linear-gradient(180deg,#111b25 0%,#0a131b 100%);
border:1px solid rgba(255,255,255,.06);
}
.brand{
position:absolute;
z-index:4;
left:24px;
top:20px;
display:grid;
line-height:1;
user-select:none;
}
.brand strong{
font:800 31px/1 Arial,sans-serif;
letter-spacing:2px;
color:#d7dde2;
text-shadow:0 2px 4px rgba(0,0,0,.5);
}
.brand span{
margin-top:7px;
font:400 14px/1 Arial,sans-serif;
letter-spacing:6px;
color:#a4afb8;
}
.vehicle-name{
position:absolute;
z-index:4;
top:23px;
left:50%;
transform:translateX(-50%);
max-width:44%;
white-space:nowrap;
overflow:hidden;
text-overflow:ellipsis;
color:#d8e0e6;
font-size:14px;
letter-spacing:.02em;
}
.connection-card{
position:absolute;
z-index:5;
top:16px;
right:18px;
display:grid;
min-width:150px;
gap:8px;
padding:11px 14px;
border-radius:17px;
background:rgba(7,13,19,.70);
border:1px solid rgba(255,255,255,.12);
backdrop-filter:blur(10px);
box-shadow:0 8px 22px rgba(0,0,0,.22);
}
.online-line{
display:flex;
align-items:center;
gap:9px;
font-size:13px;
font-weight:700;
}
.dot{
width:12px;
height:12px;
border-radius:50%;
background:var(--gwm-red);
box-shadow:0 0 0 4px rgba(255,65,65,.12),0 0 14px rgba(255,65,65,.45);
}
.connection-card.online .dot{
background:var(--gwm-green);
box-shadow:0 0 0 4px rgba(24,202,106,.12),0 0 14px rgba(24,202,106,.45);
}
.connection-card.unknown .dot{
background:#6f7a84;
box-shadow:none;
}
.gsm-line{
display:flex;
align-items:flex-end;
justify-content:space-between;
gap:12px;
color:#9ba7b0;
font-size:11px;
}
.signal-bars{
display:inline-flex;
align-items:flex-end;
gap:3px;
min-width:31px;
height:24px;
}
.signal-bars i{
width:5px;
border-radius:2px 2px 1px 1px;
background:#344450;
}
.signal-bars i.on{
background:linear-gradient(180deg,#38c2ff,#15cf72);
box-shadow:0 0 7px rgba(55,184,255,.18);
}
.jolion-scene{
position:absolute;
inset:42px 10px 4px 10px;
width:calc(100% - 20px);
height:calc(100% - 46px);
overflow:visible;
}
.vehicle-aura{fill:transparent;transition:fill .3s,filter .3s}
.lock-closed .vehicle-aura{
fill:rgba(24,202,106,.055);
filter:url(#blueGlow);
}
.lock-open .vehicle-aura{
fill:rgba(255,195,56,.06);
filter:url(#orangeGlow);
}
.car-body{
fill:url(#bodyPaint);
stroke:rgba(234,242,248,.55);
stroke-width:2.3;
}
.hood-panel,.trunk-panel{
fill:url(#bodyPaint);
stroke:rgba(224,234,241,.30);
stroke-width:1.7;
}
.hood-center{
fill:none;
stroke:rgba(25,44,58,.60);
stroke-width:1.6;
}
.roof-frame{
fill:url(#bodyDark);
stroke:rgba(255,255,255,.18);
stroke-width:1.4;
}
.glass{
fill:url(#glass);
stroke:rgba(169,196,213,.24);
stroke-width:1.2;
}
.cabin-seats rect{
fill:#101a23;
stroke:rgba(135,157,172,.13);
stroke-width:1;
}
.cabin-seats line{
stroke:rgba(142,166,182,.11);
stroke-width:2;
}
.front-bumper,.rear-bumper{
fill:none;
stroke:rgba(220,232,240,.55);
stroke-width:4;
stroke-linecap:round;
}
.headlamp{
fill:#e7f7ff;
stroke:#bcecff;
stroke-width:1.2;
opacity:.86;
}
.headlight-beam{
fill:transparent;
opacity:0;
}
.headlights.lights-on .headlamp{
fill:#fff6dc;
filter:url(#orangeGlow);
}
.headlights.lights-on .headlight-beam{
fill:rgba(255,232,181,.24);
opacity:.9;
filter:url(#orangeGlow);
animation:lightPulse 2s ease-in-out infinite;
}
.tail-light{
fill:#e7242f;
opacity:.8;
filter:url(#redGlow);
}
.engine-halo{
fill:transparent;
stroke:transparent;
stroke-width:2;
}
.engine-icon{
fill:none;
stroke:#6f7b84;
stroke-width:4;
stroke-linejoin:round;
stroke-linecap:round;
opacity:.18;
}
.engine-on .engine-halo{
fill:rgba(255,155,34,.13);
stroke:rgba(255,155,34,.65);
filter:url(#orangeGlow);
animation:enginePulse 1.5s ease-in-out infinite;
}
.engine-on .engine-icon{
stroke:var(--gwm-orange);
opacity:1;
filter:url(#orangeGlow);
animation:engineIconPulse 1.5s ease-in-out infinite;
}
.fan-ring,.fan-core,.fan-blade{
fill:#2b3944;
stroke:#627482;
stroke-width:1.4;
opacity:.18;
}
.airflow{
fill:none;
stroke:transparent;
stroke-width:6;
stroke-linecap:round;
stroke-dasharray:18 13;
}
.climate-on .fan-ring,.climate-on .fan-core,.climate-on .fan-blade{
fill:rgba(54,169,255,.24);
stroke:var(--gwm-blue);
opacity:1;
filter:url(#blueGlow);
}
.fan-blades{
transform-box:view-box;
transform-origin:657px 260px;
}
.climate-on .fan-blades{
animation:fanSpin 1.8s linear infinite;
}
.climate-on .airflow{
stroke:rgba(54,169,255,.72);
filter:url(#blueGlow);
animation:airflow 1.6s linear infinite;
}
/*
* DOOR HINGE CONTRACT:
* ALL FOUR DOORS hinge on the LEFT edge of their own SVG panel.
* top/left vehicle side opens upward; bottom/right vehicle side opens downward.
*/
.door{
transform-box:fill-box;
transform-origin:0% 50%;
transition:transform .46s cubic-bezier(.2,.8,.2,1),filter .25s;
}
.door-panel{
fill:url(#bodyDark);
stroke:rgba(222,233,240,.32);
stroke-width:1.7;
}
.door-window{
fill:url(#doorGlass);
stroke:rgba(68,154,211,.35);
stroke-width:1.1;
transform-box:fill-box;
transform-origin:center bottom;
transition:opacity .35s,transform .35s;
}
.door.left-side.open{
transform:rotate(-34deg);
filter:drop-shadow(0 -8px 11px rgba(0,0,0,.45));
}
.door.right-side.open{
transform:rotate(34deg);
filter:drop-shadow(0 8px 11px rgba(0,0,0,.45));
}
.door.open .door-panel{
stroke:rgba(54,169,255,.85);
}
.hinge{
fill:#90a0ab;
stroke:#101820;
stroke-width:1.3;
opacity:.75;
}
.unknown-door-open .door-panel{
stroke:rgba(255,65,65,.75);
animation:unknownDoorPulse 1.25s ease-in-out infinite;
}
.windows-open .generic-window{
stroke:rgba(54,169,255,.85);
filter:url(#blueGlow);
animation:windowPulse 1.4s ease-in-out infinite;
}
.trunk-lid{
transform-box:fill-box;
transform-origin:0% 50%;
transition:transform .48s cubic-bezier(.2,.8,.2,1);
}
.trunk-open .trunk-lid{
transform:translateX(34px) rotate(4deg) scale(.97);
filter:drop-shadow(10px 0 12px rgba(0,0,0,.45));
}
.trunk-open .trunk-panel{
stroke:var(--gwm-red);
stroke-width:2.5;
}
.door-state-label text,.trunk-state-label text{
fill:#98a6b1;
text-anchor:middle;
font:400 14px Arial,sans-serif;
}
.door-state-label .door-label-state,.trunk-state-label .state{
fill:#7f8d98;
font-weight:700;
}
.door-state-label.is-open .door-label-state{
fill:var(--gwm-blue);
filter:url(#blueGlow);
}
.trunk-state-label{
opacity:.88;
}
.trunk-state-label.is-open .state{
fill:var(--gwm-red);
filter:url(#redGlow);
}
.status-dock{
display:grid;
grid-template-columns:repeat(8,minmax(0,1fr));
gap:8px;
margin-top:10px;
}
.status-tile{
min-width:0;
min-height:82px;
display:grid;
grid-template-columns:auto 1fr;
align-items:center;
gap:8px;
padding:10px;
border-radius:16px;
background:linear-gradient(180deg,rgba(24,36,47,.96),rgba(13,22,31,.96));
border:1px solid rgba(255,255,255,.09);
box-shadow:inset 0 1px 0 rgba(255,255,255,.025);
}
.status-icon{
display:grid;
place-items:center;
width:34px;
height:34px;
border-radius:11px;
background:rgba(255,255,255,.035);
}
.status-icon ha-icon{--mdc-icon-size:22px;color:#a8b4bd}
.status-copy{min-width:0;display:grid;gap:4px}
.status-copy small{
font-size:10px;
color:#b2bcc4;
white-space:nowrap;
overflow:hidden;
text-overflow:ellipsis;
}
.status-copy strong{
font-size:11px;
font-weight:700;
color:#eef3f6;
white-space:nowrap;
overflow:hidden;
text-overflow:ellipsis;
}
.status-tile.engine .status-icon ha-icon,.status-tile.engine strong{color:var(--gwm-orange)}
.status-tile.climate .status-icon ha-icon,.status-tile.climate strong{color:var(--gwm-blue)}
.status-tile.warn .status-icon ha-icon,.status-tile.warn strong{color:var(--gwm-red)}
.status-tile.lock .status-icon ha-icon,.status-tile.lock strong{color:var(--gwm-green)}
.status-tile.unlock .status-icon ha-icon,.status-tile.unlock strong{color:var(--gwm-yellow)}
.status-tile.info .status-icon ha-icon{color:#c5d0d8}
.status-tile.ok .status-icon ha-icon{color:#8fa0ac}
.info-grid{
display:grid;
grid-template-columns:repeat(4,minmax(0,1fr));
gap:8px;
margin-top:10px;
}
.info-tile{
min-width:0;
display:flex;
align-items:center;
gap:8px;
padding:10px;
border-radius:14px;
background:rgba(255,255,255,.035);
border:1px solid rgba(255,255,255,.065);
}
.info-tile ha-icon{--mdc-icon-size:20px;color:var(--gwm-blue)}
.info-tile small{display:block;color:#8f9ca6;font-size:9px}
.info-tile strong{
display:block;
margin-top:2px;
color:#e9eef2;
font-size:11px;
white-space:nowrap;
overflow:hidden;
text-overflow:ellipsis;
}
.remote-controls{
display:grid;
grid-template-columns:repeat(3,minmax(0,1fr));
gap:10px;
margin-top:12px;
padding:14px 6px 4px;
border-top:1px solid rgba(255,255,255,.07);
}
.remote-action{
appearance:none;
border:0;
background:transparent;
color:#dfe7ec;
display:flex;
flex-direction:column;
align-items:center;
gap:7px;
cursor:pointer;
font:inherit;
min-width:0;
}
.remote-action>span:last-child{
width:100%;
overflow:hidden;
text-overflow:ellipsis;
white-space:nowrap;
font-size:10px;
}
.action-circle{
width:54px;
height:54px;
border-radius:50%;
display:grid;
place-items:center;
background:linear-gradient(180deg,#192732,#101a23);
border:1px solid rgba(255,255,255,.10);
box-shadow:0 6px 15px rgba(0,0,0,.22);
}
.action-circle ha-icon{--mdc-icon-size:25px;color:var(--gwm-blue)}
.remote-action.active .action-circle ha-icon{color:var(--gwm-orange)}
.remote-action.warn .action-circle ha-icon{color:var(--gwm-red)}
.remote-action.experimental .action-circle{border-style:dashed}
.remote-action.busy{opacity:.5}
.remote-action:disabled{opacity:.42;pointer-events:none}
@keyframes enginePulse{0%,100%{opacity:.45}50%{opacity:1}}
@keyframes engineIconPulse{0%,100%{stroke-width:3.5}50%{stroke-width:5}}
@keyframes fanSpin{to{transform:rotate(360deg)}}
@keyframes airflow{to{stroke-dashoffset:-62}}
@keyframes windowPulse{0%,100%{opacity:.45}50%{opacity:1}}
@keyframes unknownDoorPulse{0%,100%{opacity:.5}50%{opacity:1}}
@keyframes lightPulse{0%,100%{opacity:.45}50%{opacity:.95}}
@media(max-width:900px){
.stage{min-height:360px}
.brand strong{font-size:25px}
.brand span{font-size:11px;letter-spacing:5px}
.vehicle-name{display:none}
.status-dock{grid-template-columns:repeat(4,minmax(0,1fr))}
.status-tile{min-height:70px}
}
@media(max-width:560px){
.wrap{padding:8px}
.stage{min-height:300px;border-radius:17px}
.brand{left:15px;top:14px}
.brand strong{font-size:20px}
.brand span{font-size:9px;letter-spacing:4px;margin-top:5px}
.connection-card{top:10px;right:10px;min-width:125px;padding:8px 10px}
.online-line{font-size:11px}
.gsm-line{font-size:9px}
.jolion-scene{inset:36px 0 0 0;width:100%;height:calc(100% - 36px)}
.door-state-label,.trunk-state-label{display:none}
.status-dock{gap:6px}
.status-tile{
min-height:61px;
grid-template-columns:auto 1fr;
gap:6px;
padding:7px;
border-radius:12px;
}
.status-icon{width:28px;height:28px;border-radius:9px}
.status-icon ha-icon{--mdc-icon-size:18px}
.status-copy small{font-size:8px}
.status-copy strong{font-size:9px}
.info-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
.action-circle{width:50px;height:50px}
}
</style>
<ha-card>
<div class="wrap">
<div class="stage ${lockTone}">
<div class="brand">
<strong>GWM</strong>
<span>JOLION</span>
</div>
<div class="vehicle-name">${this._escape(this._title())}</div>
<div class="connection-card ${onlineKnown ? (online ? "online" : "offline") : "unknown"}">
<div class="online-line">
<span class="dot"></span>
<span>${onlineKnown ? (online ? "Онлайн" : "Оффлайн") : "Нет данных"}</span>
</div>
<div class="gsm-line">
<span>GSM</span>
${this._signalBars()}
</div>
</div>
${this._carSvg()}
</div>
${this._renderStatuses()}
${this._renderInfo()}
${this._renderControls()}
</div>
</ha-card>
`;
this.shadowRoot.querySelectorAll("[data-action]").forEach((button) => {
button.addEventListener("click", () => this._handleAction(button.dataset.action));
});
}
_confirm(message) {
return this._config.confirm_controls === false || window.confirm(message);
}
async _runBusy(key, fn, onSuccess = null) {
if (this._busy.has(key)) return;
this._busy.add(key);
this._render();
try {
await fn();
if (onSuccess) onSuccess();
} catch (error) {
console.error(`[GWM Jolion Remote Card] ${key} failed`, error);
alert(`GWM Jolion: ${error?.message || String(error)}`);
} finally {
this._busy.delete(key);
this._render();
}
}
async _handleAction(action) {
if (!this._hass) return;
const unlocked = this._isOn("unlocked");
const engine = this._isOn("engine");
const climate = this._climateOn();
const trunk = this._isOn("trunk");
const windows = this._isOn("windows");
if (action === "lock") {
const entityId = this._entities.lock;
if (!entityId) return alert("GWM Jolion: сущность замка не найдена");
if (!this._confirm(unlocked ? "Закрыть автомобиль?" : "Разблокировать автомобиль?")) return;
return this._runBusy(action, () =>
this._hass.callService("lock", unlocked ? "lock" : "unlock", { entity_id: entityId }),
);
}
if (action === "engine") {
if (!engine) {
const blockers = [];
if (unlocked) blockers.push("автомобиль не закрыт");
if (this._isOn("doors")) blockers.push("открыта дверь");
if (trunk) blockers.push("открыт багажник");
if (blockers.length) {
return alert(`GWM Jolion: запуск недоступен — ${blockers.join(", ")}.`);
}
}
if (!this._confirm(engine ? "Остановить двигатель?" : "Запустить двигатель на 15 минут?")) return;
return this._runBusy(action, () =>
this._hass.callService(
INTEGRATION,
engine ? "stop_engine" : "start_engine",
engine ? {} : { operation_time: 15 },
),
);
}
if (action === "climate") {
const entityId = this._entities.climate;
if (!entityId) return alert("GWM Jolion: сущность климата не найдена");
if (
!this._confirm(
climate
? "Выключить климат?"
: "Включить климат? На автомобиле с ДВС может запуститься двигатель.",
)
) {
return;
}
return this._runBusy(action, () =>
this._hass.callService("climate", climate ? "turn_off" : "turn_on", {
entity_id: entityId,
}),
);
}
if (action === "trunk") {
if (!this._confirm(trunk ? "Закрыть багажник?" : "Открыть багажник?")) return;
return this._runBusy(action, () =>
this._hass.callService(INTEGRATION, trunk ? "close_trunk" : "open_trunk", {}),
);
}
if (action === "windows") {
if (
!this._confirm(
windows
? "Закрыть все окна?"
: "Открыть все окна? Команда открытия экспериментальная.",
)
) {
return;
}
return this._runBusy(action, () =>
this._hass.callService(INTEGRATION, windows ? "close_windows" : "open_windows", {}),
);
}
if (action === "refresh") {
const entityId = this._entities.refresh;
if (!entityId) return alert("GWM Jolion: кнопка обновления не найдена");
return this._runBusy(action, () =>
this._hass.callService("button", "press", { entity_id: entityId }),
);
}
if (action === "steering") {
return this._toggleComfort(
action,
"steeringHeat",
"steering_wheel_heat_on",
"steering_wheel_heat_off",
"обогрев руля",
);
}
if (action === "rear_defrost") {
return this._toggleComfort(
action,
"rearDefrost",
"rear_defrost_on",
"rear_defrost_off",
"обогрев заднего стекла",
);
}
if (action === "front_defrost") {
return this._toggleComfort(
action,
"frontDefrost",
"front_defrost_on",
"front_defrost_off",
"передний defrost",
);
}
if (action === "sunroof") {
return this._toggleRoof(
action,
"sunroofOpen",
"open_sunroof",
"close_sunroof",
"панораму",
);
}
if (action === "sunshade") {
return this._toggleRoof(
action,
"sunshadeOpen",
"open_sunshade",
"close_sunshade",
"шторку",
);
}
}
async _toggleComfort(action, key, onService, offService, label) {
const current = !this._isUnavailable(key)
? this._isOn(key)
: Boolean(this._assumed[key]);
const next = !current;
if (!this._confirm(`${next ? "Включить" : "Выключить"} ${label}?`)) return;
return this._runBusy(
action,
() => this._hass.callService(INTEGRATION, next ? onService : offService, {}),
() => {
this._assumed[key] = next;
},
);
}
async _toggleRoof(action, key, openService, closeService, label) {
let current = this._assumed[key];
if (current === undefined) {
const open = window.confirm(
`${label[0].toUpperCase()}${label.slice(1)}: ОК — открыть, Отмена — закрыть.`,
);
current = !open;
}
const next = !current;
if (
this._config.confirm_controls !== false &&
!this._confirm(`${next ? "Открыть" : "Закрыть"} ${label}?`)
) {
return;
}
return this._runBusy(
action,
() => this._hass.callService(INTEGRATION, next ? openService : closeService, {}),
() => {
this._assumed[key] = next;
},
);
}
}
if (!customElements.get("gwm-jolion-remote-card-editor")) {
customElements.define("gwm-jolion-remote-card-editor", GwmJolionRemoteCardEditor);
}
if (!customElements.get("gwm-jolion-remote-card")) {
customElements.define("gwm-jolion-remote-card", GwmJolionRemoteCard);
}
window.customCards = window.customCards || [];
if (!window.customCards.some((card) => card.type === "gwm-jolion-remote-card")) {
window.customCards.push({
type: "gwm-jolion-remote-card",
name: "GWM Jolion — анимированный пульт",
description: "Горизонтальный top-view GWM Jolion с отдельной анимацией дверей, багажника, двигателя и климата",
preview: true,
documentationURL: "https://github.com/IndeecDen/ha-gwm-jolion",
});
}
console.info(
`%c GWM JOLION REMOTE CARD %c ${CARD_VERSION} `,
"background:#0f1922;color:white;font-weight:bold;padding:2px 6px;border-radius:3px",
"background:#526474;color:white;padding:2px 6px;border-radius:3px",
);
})();
