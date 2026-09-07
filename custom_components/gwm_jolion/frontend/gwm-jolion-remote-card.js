/* GWM Jolion Remote Card v0.1.0-alpha.19.7 */
(() => {
  const CARD_VERSION = "0.1.0-alpha.19.7";
  const INTEGRATION = "gwm_jolion";
  const DEFAULT_CONTROLS = ["lock", "engine", "climate", "trunk", "refresh"];
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
    ["defrost", "Defrost"],
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
    window2: "_window_2210002_open",
    window2Raw: "_window_2210002_raw",
    window3: "_window_2210003_open",
    window3Raw: "_window_2210003_raw",
    window4: "_window_2210004_open",
    window4Raw: "_window_2210004_raw",
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
        car_color: "#7b8792",
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
            ${options.map(([value, label]) => `
              <label>
                <input type="checkbox" data-list="${key}" data-value="${value}" ${selected.includes(value) ? "checked" : ""}>
                <span>${label}</span>
              </label>
            `).join("")}
          </div>
        </section>
      `;
    }

    _render() {
      if (!this.shadowRoot) return;
      const color = /^#[0-9a-f]{6}$/i.test(this._config.car_color || "") ? this._config.car_color : "#7b8792";
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
          .note{padding:10px 12px;border-radius:10px;background:color-mix(in srgb,var(--primary-color) 7%,transparent);font-size:12px;color:var(--secondary-text-color);line-height:1.5}
          @media(max-width:520px){.grid{grid-template-columns:1fr}}
        </style>
        <div class="editor">
          <div class="row">
            <label class="field">Название
              <input id="title" type="text" value="${this._escape(this._config.title || "")}" placeholder="Haval Jolion">
            </label>
            <label class="field">Цвет
              <input id="color" type="color" value="${color}">
            </label>
          </div>
          <label class="check"><input id="confirm" type="checkbox" ${this._config.confirm_controls !== false ? "checked" : ""}>Подтверждать удалённые команды</label>
          ${this._group("Кнопки управления", "controls", CONTROL_OPTIONS)}
          ${this._group("Дополнительная информация", "info", INFO_OPTIONS)}
          ${this._group("Статусные плитки", "statuses", STATUS_OPTIONS)}
          <div class="note">
            Ориентация alpha.19.6: капот слева, багажник справа; верх карточки — правая сторона автомобиля (FR/RR), низ — левая (FL/RL).
            Карточка использует широкие SUV-пропорции и всегда показывает значения статусов отдельным текстом.
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
              ? (current.includes(value) ? current : [...current, value])
              : current.filter((item) => item !== value),
          });
        });
      });

      this.shadowRoot.getElementById("confirm")?.addEventListener("change", (event) =>
        this._emit({ ...this._config, confirm_controls: event.target.checked }),
      );

      this.shadowRoot.getElementById("title")?.addEventListener("change", (event) => {
        const next = { ...this._config };
        const value = String(event.target.value || "").trim();
        if (value) next.title = value;
        else delete next.title;
        this._emit(next);
      });

      this.shadowRoot.getElementById("color")?.addEventListener("change", (event) =>
        this._emit({ ...this._config, car_color: event.target.value }),
      );
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
      return { columns: 12, rows: 12, min_columns: 6, min_rows: 8 };
    }

    setConfig(config) {
      this._config = {
        controls: [...DEFAULT_CONTROLS],
        info: [...DEFAULT_INFO],
        statuses: [...DEFAULT_STATUSES],
        confirm_controls: true,
        car_color: "#7b8792",
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
      return 12;
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
        const entries = deviceId ? gwmEntries.filter((entry) => entry.device_id === deviceId) : gwmEntries;

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

    _value(key, fallback = "Нет данных") {
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
      return /^#[0-9a-f]{6}$/i.test(this._config.car_color || "") ? this._config.car_color : "#7b8792";
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
      return this._isOn("climateOn") || ["heat_cool", "heat", "cool", "fan_only"].includes(climate?.state);
    }

    _windowLevel(raw) {
      const value = Number(raw);
      if (value === 1) return 0;
      if (value === 3) return 0.52;
      if (value === 2) return 1;
      return null;
    }

    _windowVisual(openKey, rawKey) {
      const rawLevel = this._windowLevel(this._raw(rawKey));
      const level = rawLevel === null
        ? (this._isUnavailable(openKey) ? null : this._isOn(openKey) ? 1 : 0)
        : rawLevel;
      return {
        level,
        open: level !== null && level > 0,
        opacity: level === null ? 0.94 : Math.max(0.08, 0.96 - level * 0.88),
        scale: level === null ? 1 : Math.max(0.18, 1 - level * 0.76),
      };
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
          ${[1, 2, 3, 4].map((index) =>
            `<i class="${known && index <= raw ? "on" : ""}" style="height:${8 + index * 4}px"></i>`
          ).join("")}
        </span>
      `;
    }

    _doorCallout(kind, open) {
      const labels = {
        fr: ["Передняя правая", 37, 18, "top front"],
        rr: ["Задняя правая", 64, 18, "top rear"],
        fl: ["Передняя левая", 37, 82, "bottom front"],
        rl: ["Задняя левая", 64, 82, "bottom rear"],
      };
      const [title, left, top, classes] = labels[kind];
      return `
        <div class="door-callout ${classes} ${open ? "open" : ""}" style="left:${left}%;top:${top}%">
          <span>${title}</span>
          <strong>${open ? "Открыта" : "Закрыта"}</strong>
          <i></i>
        </div>
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
      const specificKnown = ["doorFl", "doorFr", "doorRl", "doorRr"].some((key) => !this._isUnavailable(key));
      const unknownDoorOpen = aggregateDoors && !specificKnown;
      const windowFl = this._windowVisual("window1", "window1Raw");
      const windowFr = this._windowVisual("window2", "window2Raw");
      const windowRl = this._windowVisual("window3", "window3Raw");
      const windowRr = this._windowVisual("window4", "window4Raw");
      const anyWindows = this._isOn("windows") || [windowFl, windowFr, windowRl, windowRr].some((item) => item.open);

      return `
        <div class="car-scene ${lockClass} ${engine ? "engine-on" : ""} ${climate ? "climate-on" : ""} ${trunk ? "trunk-open" : ""} ${anyWindows ? "windows-open" : ""} ${unknownDoorOpen ? "unknown-door-open" : ""}">
          ${this._doorCallout("fr", doors.fr)}
          ${this._doorCallout("rr", doors.rr)}
          ${this._doorCallout("fl", doors.fl)}
          ${this._doorCallout("rl", doors.rl)}

          <div class="trunk-callout ${trunk ? "open" : ""}">
            <span>Багажник</span>
            <strong>${trunk ? "Открыт" : "Закрыт"}</strong>
            <i></i>
          </div>

          <svg class="jolion-scene" viewBox="0 0 1100 520" role="img" aria-label="Haval Jolion вид сверху: капот слева, багажник справа, правая сторона автомобиля сверху, левая снизу">
            <defs>
              <linearGradient id="paint" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0" stop-color="color-mix(in srgb,var(--gwm-car-color) 35%,white 65%)"/>
                <stop offset=".18" stop-color="color-mix(in srgb,var(--gwm-car-color) 72%,white 28%)"/>
                <stop offset=".52" stop-color="var(--gwm-car-color)"/>
                <stop offset="1" stop-color="color-mix(in srgb,var(--gwm-car-color) 58%,black 42%)"/>
              </linearGradient>
              <linearGradient id="paintDark" x1="0" x2="1">
                <stop offset="0" stop-color="color-mix(in srgb,var(--gwm-car-color) 76%,black 24%)"/>
                <stop offset="1" stop-color="color-mix(in srgb,var(--gwm-car-color) 46%,black 54%)"/>
              </linearGradient>
              <linearGradient id="glass" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0" stop-color="#35536a"/>
                <stop offset=".30" stop-color="#172e40"/>
                <stop offset=".72" stop-color="#0b1c29"/>
                <stop offset="1" stop-color="#06121b"/>
              </linearGradient>
              <filter id="shadow" x="-30%" y="-40%" width="160%" height="180%">
                <feDropShadow dx="0" dy="12" stdDeviation="16" flood-color="#000" flood-opacity=".62"/>
              </filter>
              <filter id="blueGlow" x="-100%" y="-100%" width="300%" height="300%">
                <feGaussianBlur stdDeviation="8" result="b"/>
                <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
              </filter>
              <filter id="orangeGlow" x="-100%" y="-100%" width="300%" height="300%">
                <feGaussianBlur stdDeviation="10" result="b"/>
                <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
              </filter>
              <filter id="redGlow" x="-100%" y="-100%" width="300%" height="300%">
                <feGaussianBlur stdDeviation="8" result="b"/>
                <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
              </filter>
            </defs>

            <!-- GEOMETRY CONTRACT alpha.19.6: wide SUV proportions, hood left, trunk right, TOP=RIGHT side (FR/RR), BOTTOM=LEFT side (FL/RL). -->
            <ellipse class="vehicle-aura" cx="560" cy="260" rx="442" ry="190"/>

            <g class="vehicle" filter="url(#shadow)">
              <path class="body" d="M118 260 C128 171 190 116 300 84 C430 48 760 48 880 84 C958 107 1004 171 1018 260 C1004 349 958 413 880 436 C760 472 430 472 300 436 C190 404 128 349 118 260 Z"/>

              <path class="hood" d="M132 260 C143 188 194 138 292 111 L392 86 C420 128 434 184 434 260 C434 336 420 392 392 434 L292 409 C194 382 143 332 132 260 Z"/>
              <path class="hood-lines" d="M171 260 C185 211 222 172 305 145 L376 125 M171 260 C185 309 222 348 305 375 L376 395"/>
              <path class="grille" d="M126 211 Q112 260 126 309 M139 219 Q128 260 139 301 M152 226 Q144 260 152 294"/>

              <path class="roof-shell" d="M419 96 C506 68 738 68 835 95 L900 143 L900 377 L835 425 C738 452 506 452 419 424 L390 373 L390 147 Z"/>
              <path class="windshield front" d="M431 119 C465 91 505 79 548 75 L548 445 C505 441 465 429 431 401 L408 365 L408 155 Z"/>
              <path class="cabin" d="M561 77 L802 84 C837 86 867 104 887 141 L887 379 C867 416 837 434 802 436 L561 443 Z"/>
              <path class="windshield rear" d="M804 88 C839 91 865 109 884 142 L884 378 C865 411 839 429 804 432 Z"/>

              <g class="panoramic-roof">
                <rect x="588" y="107" width="183" height="120" rx="18"/>
                <rect x="588" y="293" width="183" height="120" rx="18"/>
                <line x1="780" y1="107" x2="780" y2="413"/>
              </g>

              <g class="seat-layout">
                <rect x="584" y="126" width="82" height="96" rx="26"/>
                <rect x="584" y="298" width="82" height="96" rx="26"/>
                <rect x="701" y="126" width="82" height="96" rx="26"/>
                <rect x="701" y="298" width="82" height="96" rx="26"/>
                <line x1="683" y1="102" x2="683" y2="418"/>
              </g>

              <g class="engine-visual">
                <ellipse class="engine-halo" cx="280" cy="260" rx="78" ry="90"/>
                <path class="engine-icon" d="M244 236h71v52h-71z M258 223h42v13 M234 246h10 M315 246h13v32h-13 M263 288v13h34v-13"/>
              </g>

              <g class="climate-visual">
                <circle class="fan-ring" cx="685" cy="260" r="28"/>
                <circle class="fan-core" cx="685" cy="260" r="8"/>
                <g class="fan-blades">
                  <path d="M685 251 C666 236 665 221 679 216 C693 213 698 234 685 251Z"/>
                  <path d="M694 260 C709 241 724 240 729 254 C733 268 712 273 694 260Z"/>
                  <path d="M685 269 C704 284 705 299 691 304 C677 307 672 286 685 269Z"/>
                  <path d="M676 260 C661 279 646 280 641 266 C637 252 658 247 676 260Z"/>
                </g>
                <path class="airflow" d="M661 247 C625 218 605 192 583 159"/>
                <path class="airflow" d="M661 273 C625 302 605 328 583 361"/>
                <path class="airflow" d="M709 247 C745 218 766 192 790 160"/>
                <path class="airflow" d="M709 273 C745 302 766 328 790 360"/>
              </g>

              <g class="headlights">
                <path class="headlamp" d="M145 166 C175 129 218 111 272 102 L298 121 L214 167 Z"/>
                <path class="headlamp" d="M145 354 C175 391 218 409 272 418 L298 399 L214 353 Z"/>
                <path class="headlight-beam" d="M151 162 L22 96 L48 207 Z"/>
                <path class="headlight-beam" d="M151 358 L22 424 L48 313 Z"/>
              </g>

              <g class="tail-lights">
                <path d="M944 132 C978 154 998 188 1006 220 L981 228 L925 176 Z"/>
                <path d="M944 388 C978 366 998 332 1006 300 L981 292 L925 344 Z"/>
              </g>

              <g class="roof-rails">
                <path d="M454 103 C548 82 710 82 809 100"/>
                <path d="M454 417 C548 438 710 438 809 420"/>
              </g>

              <g class="mirrors">
                <path d="M421 95 L392 67 L365 81 L395 119 Z"/>
                <path d="M421 425 L392 453 L365 439 L395 401 Z"/>
              </g>

              <g class="door door-fr top-side ${doors.fr ? "open" : ""}">
                <path class="door-panel" d="M410 111 L586 78 L586 166 L410 188 Z"/>
                <path class="door-window ${windowFr.open ? "window-open" : ""}" d="M435 119 L565 95 L565 151 L435 168 Z" style="opacity:${windowFr.opacity.toFixed(2)};transform:scaleY(${windowFr.scale.toFixed(2)})"/>
              </g>
              <circle class="hinge hinge-fr" cx="410" cy="150" r="5"/>

              <g class="door door-rr top-side ${doors.rr ? "open" : ""}">
                <path class="door-panel" d="M602 76 L828 89 L828 177 L602 166 Z"/>
                <path class="door-window ${windowRr.open ? "window-open" : ""}" d="M625 94 L805 104 L805 158 L625 151 Z" style="opacity:${windowRr.opacity.toFixed(2)};transform:scaleY(${windowRr.scale.toFixed(2)})"/>
              </g>
              <circle class="hinge hinge-rr" cx="602" cy="121" r="5"/>

              <g class="door door-fl bottom-side ${doors.fl ? "open" : ""}">
                <path class="door-panel" d="M410 409 L586 442 L586 354 L410 332 Z"/>
                <path class="door-window driver-window ${windowFl.open ? "window-open" : ""}" d="M435 401 L565 425 L565 369 L435 352 Z" style="opacity:${windowFl.opacity.toFixed(2)};transform:scaleY(${windowFl.scale.toFixed(2)})"/>
              </g>
              <circle class="hinge hinge-fl" cx="410" cy="370" r="5"/>

              <g class="door door-rl bottom-side ${doors.rl ? "open" : ""}">
                <path class="door-panel" d="M602 444 L828 431 L828 343 L602 354 Z"/>
                <path class="door-window ${windowRl.open ? "window-open" : ""}" d="M625 426 L805 416 L805 362 L625 369 Z" style="opacity:${windowRl.opacity.toFixed(2)};transform:scaleY(${windowRl.scale.toFixed(2)})"/>
              </g>
              <circle class="hinge hinge-rl" cx="602" cy="399" r="5"/>

              <g class="trunk-lid">
                <path class="trunk-panel" d="M895 142 C950 157 983 198 995 260 C983 322 950 363 895 378 Z"/>
                <path class="trunk-glass" d="M914 165 C951 178 973 211 981 260 C973 309 951 342 914 355 Z"/>
              </g>

              <path class="bumper front" d="M124 215 C105 235 104 285 124 305"/>
              <path class="bumper rear" d="M1012 215 C1032 235 1033 285 1012 305"/>
            </g>
          </svg>
        </div>
      `;
    }

    _doorSummary() {
      const count = this._doorCount();
      if (count === null) {
        if (this._isUnavailable("doors")) return "Нет данных";
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
      const defrost = !this._isUnavailable("rearDefrost") && this._isOn("rearDefrost");
      const unknown = (key) => this._isUnavailable(key);

      return {
        engine: [
          "mdi:engine",
          "Двигатель",
          unknown("engine") ? "Нет данных" : engine ? "Работает" : "Выключен",
          engine ? "engine" : "ok",
        ],
        climate: [
          "mdi:fan",
          "Климат",
          !this._state("climate") && unknown("climateOn") ? "Нет данных" : climate ? "Включён" : "Выключен",
          climate ? "climate" : "ok",
        ],
        fuel: ["mdi:fuel", "Топливо", this._value("fuel", "Нет данных"), "info"],
        mileage: ["mdi:counter", "Пробег", this._value("mileage", "Нет данных"), "info"],
        doors: ["mdi:car-door", "Двери", this._doorSummary(), this._isOn("doors") ? "warn" : "ok"],
        windows: [
          "mdi:car-door",
          "Окна",
          unknown("windows") ? "Нет данных" : windows ? "Открыты" : "Закрыты",
          windows ? "warn" : "ok",
        ],
        trunk: [
          "mdi:car-back",
          "Багажник",
          unknown("trunk") ? "Нет данных" : trunk ? "Открыт" : "Закрыт",
          trunk ? "warn" : "ok",
        ],
        lock: [
          unlocked ? "mdi:lock-open-variant" : "mdi:lock",
          "Замок",
          unknown("unlocked") ? "Нет данных" : unlocked ? "Разблокирован" : "Закрыт",
          unlocked ? "unlock" : "lock",
        ],
        defrost: [
          "mdi:car-defrost-rear",
          "Defrost",
          this._isUnavailable("rearDefrost") ? "Нет данных" : defrost ? "Включён" : "Выключен",
          defrost ? "climate" : "ok",
        ],
      }[id] || null;
    }

    _renderStatuses() {
      const selected = Array.isArray(this._config.statuses) ? this._config.statuses : DEFAULT_STATUSES;
      return `
        <div class="status-dock">
          ${selected.map((id) => {
            const meta = this._statusMeta(id);
            return meta ? `
              <div class="status-tile ${meta[3]}" data-status="${id}">
                <span class="status-icon">${this._icon(meta[0])}</span>
                <span class="status-copy">
                  <small>${this._escape(meta[1])}</small>
                  <strong>${this._escape(meta[2])}</strong>
                </span>
              </div>
            ` : "";
          }).join("")}
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
        tires: ["mdi:car-tire-alert", "Шины", pressures.length ? pressures.join(" / ") : "Нет данных"],
        gsm: ["mdi:signal", "GSM", `${this._raw("signal") ?? "—"}/4`],
        gps: ["mdi:crosshairs-gps", "GPS", this._isUnavailable("gps") ? "Нет данных" : this._isOn("gps") ? "есть" : "нет"],
        climate: ["mdi:air-conditioner", "Климат", this._climateOn() ? "работает" : "выключен"],
        oil: ["mdi:oil", "Масло", this._raw("oilQty") === null ? "Нет данных" : `${this._raw("oilQty")}/8`],
        update: ["mdi:cloud-sync", "Обновление", this._relativeUpdate()],
      }[id] || null;
    }

    _renderInfo() {
      const selected = Array.isArray(this._config.info) ? this._config.info : DEFAULT_INFO;
      const items = selected.map((id) => this._infoMeta(id)).filter(Boolean);
      return items.length ? `
        <div class="info-grid">
          ${items.map((meta) => `
            <div class="info-tile">
              ${this._icon(meta[0])}
              <div>
                <small>${this._escape(meta[1])}</small>
                <strong>${this._escape(meta[2])}</strong>
              </div>
            </div>
          `).join("")}
        </div>
      ` : "";
    }

    _controlMeta(id) {
      const feature = FEATURE_BY_CONTROL[id];
      if (feature && !this._featureEnabled(feature)) return null;

      const unlocked = this._isOn("unlocked");
      const engine = this._isOn("engine");
      const climate = this._climateOn();
      const trunk = this._isOn("trunk");
      const windows = this._isOn("windows");
      const steering = !this._isUnavailable("steeringHeat") ? this._isOn("steeringHeat") : Boolean(this._assumed.steeringHeat);
      const rear = !this._isUnavailable("rearDefrost") ? this._isOn("rearDefrost") : Boolean(this._assumed.rearDefrost);
      const front = !this._isUnavailable("frontDefrost") ? this._isOn("frontDefrost") : Boolean(this._assumed.frontDefrost);

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
        climate: ["mdi:air-conditioner", climate ? "Климат выкл." : "Климат вкл.", climate ? "active climate" : "", false],
        trunk: ["mdi:car-back", trunk ? "Закрыть багажник" : "Открыть багажник", trunk ? "warn" : "", this._isUnavailable("trunk")],
        windows: ["mdi:car-door", windows ? "Закрыть окна" : "Открыть окна", windows ? "warn" : "", this._isUnavailable("windows")],
        refresh: ["mdi:refresh", "Обновить", "", false],
        steering: ["mdi:steering", steering ? "Руль выкл." : "Руль вкл.", steering ? "active" : "", false],
        rear_defrost: ["mdi:car-defrost-rear", rear ? "Заднее выкл." : "Defrost вкл.", rear ? "active" : "", false],
        front_defrost: ["mdi:car-defrost-front", front ? "Defrost выкл." : "Defrost вкл.", front ? "active" : "experimental", false],
        sunroof: ["mdi:car-select", "Панорама", "experimental", false],
        sunshade: ["mdi:blinds", "Шторка", "experimental", false],
      }[id] || null;
    }

    _renderControls() {
      const selected = Array.isArray(this._config.controls) ? this._config.controls : DEFAULT_CONTROLS;
      const remoteBusy = this._remoteBusy();
      const items = selected.map((id) => {
        const meta = this._controlMeta(id);
        if (!meta) return "";
        const busy = this._busy.has(id) || (remoteBusy && id !== "refresh");
        const disabled = meta[3] || busy;
        return `
          <button class="remote-action ${meta[2]} ${busy ? "busy" : ""}" ${disabled ? "disabled" : `data-action="${id}"`}>
            <span class="action-circle">${this._icon(meta[0])}</span>
            <span>${this._escape(meta[1])}</span>
          </button>
        `;
      }).join("");
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

      this.shadowRoot.innerHTML = `
        <style>
          :host{
            display:block;
            --gwm-car-color:${this._safeColor()};
            --gwm-text:#f3f6f8;
            --gwm-muted:#8e9ba5;
            --gwm-blue:#39adff;
            --gwm-orange:#ff9e2c;
            --gwm-red:#ff4048;
            --gwm-green:#1dce71;
            --gwm-yellow:#ffc43a;
          }

          *{box-sizing:border-box}
          ha-card{
            overflow:hidden;
            border-radius:var(--ha-card-border-radius,24px);
            background:
              radial-gradient(circle at 50% -18%,rgba(49,83,108,.30),transparent 46%),
              linear-gradient(180deg,#0d1923 0%,#071119 100%);
            color:var(--gwm-text);
            border:1px solid rgba(255,255,255,.085);
          }

          .wrap{padding:12px;container-type:inline-size}

          .hero{
            position:relative;
            min-height:450px;
            overflow:hidden;
            border-radius:22px;
            background:
              radial-gradient(ellipse at 50% 54%,rgba(69,104,129,.18),transparent 60%),
              linear-gradient(180deg,#0d1822,#08121a);
            border:1px solid rgba(255,255,255,.065);
          }

          .brand{
            position:absolute;
            z-index:20;
            left:24px;
            top:20px;
            display:grid;
            line-height:1;
            user-select:none;
          }
          .brand strong{
            font:800 34px/1 Arial,sans-serif;
            letter-spacing:2px;
            color:#e2e7eb;
            text-shadow:0 2px 4px #000;
          }
          .brand span{
            margin-top:8px;
            font:400 14px/1 Arial,sans-serif;
            letter-spacing:6px;
            color:#a8b3bc;
          }

          .vehicle-name{
            position:absolute;
            z-index:20;
            left:50%;
            top:25px;
            transform:translateX(-50%);
            max-width:42%;
            white-space:nowrap;
            overflow:hidden;
            text-overflow:ellipsis;
            font-size:16px;
            font-weight:600;
            color:#edf2f5;
          }

          .connection-card{
            position:absolute;
            z-index:20;
            right:18px;
            top:16px;
            min-width:154px;
            padding:12px 14px;
            border-radius:18px;
            background:rgba(5,12,18,.82);
            border:1px solid rgba(255,255,255,.14);
            box-shadow:0 8px 24px rgba(0,0,0,.28);
            backdrop-filter:blur(8px);
          }
          .online-line,.gsm-line{
            display:flex;
            align-items:center;
            justify-content:space-between;
            gap:10px;
          }
          .online-line{font-size:13px;font-weight:750}
          .gsm-line{margin-top:10px;color:#9aa6af;font-size:11px;align-items:flex-end}
          .dot{
            width:13px;
            height:13px;
            border-radius:50%;
            background:var(--gwm-red);
            box-shadow:0 0 0 5px rgba(255,64,72,.12),0 0 14px rgba(255,64,72,.45);
          }
          .connection-card.online .dot{
            background:var(--gwm-green);
            box-shadow:0 0 0 5px rgba(29,206,113,.12),0 0 14px rgba(29,206,113,.45);
          }
          .connection-card.unknown .dot{background:#68747d;box-shadow:none}

          .signal-bars{display:inline-flex;align-items:flex-end;gap:3px;height:28px}
          .signal-bars i{width:6px;border-radius:2px 2px 1px 1px;background:#30414d}
          .signal-bars i.on{background:linear-gradient(180deg,#39c0ff,#18cd74)}

          .car-scene{
            position:absolute;
            left:0;
            right:0;
            top:72px;
            bottom:4px;
          }

          .jolion-scene{
            position:absolute;
            left:1.5%;
            top:52%;
            width:97%;
            height:auto;
            transform:translateY(-47%);
            overflow:visible;
          }

          .vehicle-aura{fill:transparent}
          .lock-closed .vehicle-aura{fill:rgba(29,206,113,.055);filter:url(#blueGlow)}
          .lock-open .vehicle-aura{fill:rgba(255,196,58,.075);filter:url(#orangeGlow)}

          .body,.hood,.roof-shell,.trunk-panel{
            fill:url(#paint);
            stroke:rgba(236,244,249,.50);
            stroke-width:2.2;
          }
          .hood-lines,.grille{
            fill:none;
            stroke:rgba(24,42,55,.58);
            stroke-width:2;
            stroke-linecap:round;
          }
          .windshield,.cabin,.trunk-glass{
            fill:url(#glass);
            stroke:rgba(169,200,218,.24);
            stroke-width:1.4;
          }
          .panoramic-roof rect{
            fill:rgba(4,13,20,.68);
            stroke:rgba(94,136,162,.20);
            stroke-width:1.2;
          }
          .panoramic-roof line,
          .seat-layout line{
            stroke:rgba(139,168,187,.13);
            stroke-width:2;
          }
          .seat-layout rect{
            fill:#0d1a24;
            stroke:rgba(139,168,187,.14);
          }
          .roof-rails path{
            fill:none;
            stroke:rgba(224,234,240,.50);
            stroke-width:6;
            stroke-linecap:round;
          }
          .mirrors path{
            fill:url(#paintDark);
            stroke:rgba(237,243,247,.45);
            stroke-width:1.5;
          }
          .bumper{
            fill:none;
            stroke:rgba(223,235,243,.62);
            stroke-width:5;
            stroke-linecap:round;
          }

          .headlamp{
            fill:#effbff;
            stroke:#c8efff;
            stroke-width:1.3;
            opacity:.94;
          }
          .headlight-beam{fill:transparent;opacity:0}
          .tail-lights path{
            fill:#f32638;
            opacity:.92;
            filter:url(#redGlow);
          }

          .engine-halo{fill:transparent;stroke:transparent}
          .engine-icon{
            fill:none;
            stroke:#64727c;
            stroke-width:5;
            stroke-linejoin:round;
            stroke-linecap:round;
            opacity:.15;
          }
          .engine-on .engine-halo{
            fill:rgba(255,158,44,.15);
            stroke:rgba(255,158,44,.72);
            stroke-width:2.4;
            filter:url(#orangeGlow);
            animation:enginePulse 1.45s ease-in-out infinite;
          }
          .engine-on .engine-icon{
            stroke:var(--gwm-orange);
            opacity:1;
            filter:url(#orangeGlow);
            animation:engineIconPulse 1.45s ease-in-out infinite;
          }

          .fan-ring,.fan-core,.fan-blades path{
            fill:#25343f;
            stroke:#637684;
            stroke-width:1.4;
            opacity:.14;
          }
          .airflow{
            fill:none;
            stroke:transparent;
            stroke-width:6;
            stroke-linecap:round;
            stroke-dasharray:17 13;
          }
          .fan-blades{transform-box:view-box;transform-origin:685px 260px}
          .climate-on .fan-ring,
          .climate-on .fan-core,
          .climate-on .fan-blades path{
            fill:rgba(57,173,255,.25);
            stroke:var(--gwm-blue);
            opacity:1;
            filter:url(#blueGlow);
          }
          .climate-on .fan-blades{animation:fanSpin 1.8s linear infinite}
          .climate-on .airflow{
            stroke:rgba(57,173,255,.82);
            filter:url(#blueGlow);
            animation:airflow 1.5s linear infinite;
          }

          .door{
            transform-box:fill-box;
            transform-origin:0% 50%;
            transition:transform .48s cubic-bezier(.2,.8,.2,1),filter .25s;
          }
          .door-panel{
            fill:url(#paintDark);
            stroke:rgba(227,237,244,.38);
            stroke-width:2;
          }
          .door-window{
            fill:url(#glass);
            stroke:rgba(70,158,216,.34);
            stroke-width:1.2;
            transform-box:fill-box;
            transform-origin:center bottom;
            transition:opacity .35s,transform .35s;
          }
          .door.top-side.open{transform:rotate(-31deg)}
          .door.bottom-side.open{transform:rotate(31deg)}
          .door.open .door-panel{stroke:rgba(57,173,255,.98);stroke-width:2.5}
          .hinge{
            fill:#a5b0b8;
            stroke:#07131b;
            stroke-width:1.2;
            opacity:.9;
          }
          .unknown-door-open .door-panel{
            stroke:rgba(255,64,72,.88);
            animation:unknownDoorPulse 1.2s ease-in-out infinite;
          }
          .door-window.window-open{
            stroke:rgba(57,173,255,.86);
            animation:windowPulse 1.3s ease-in-out infinite;
          }

          .trunk-lid{
            transform-box:fill-box;
            transform-origin:0% 50%;
            transition:transform .50s cubic-bezier(.2,.8,.2,1);
          }
          .trunk-open .trunk-lid{transform:translateX(48px) rotate(4deg) scale(.97)}
          .trunk-open .trunk-panel{stroke:var(--gwm-red);stroke-width:3}

          .door-callout,.trunk-callout{
            position:absolute;
            z-index:12;
            display:grid;
            gap:3px;
            min-width:118px;
            text-align:center;
            transform:translate(-50%,-50%);
            pointer-events:none;
          }
          .door-callout span,.trunk-callout span{
            font-size:12px;
            color:#c3ccd2;
            white-space:nowrap;
          }
          .door-callout strong,.trunk-callout strong{
            font-size:12px;
            color:#84939e;
          }
          .door-callout.open strong{color:var(--gwm-blue)}
          .trunk-callout{
            left:92%;
            top:51%;
            transform:translate(-50%,-50%);
            text-align:left;
            min-width:82px;
          }
          .trunk-callout.open strong{color:var(--gwm-red)}
          .door-callout i,.trunk-callout i{
            position:absolute;
            height:1px;
            background:rgba(80,179,239,.62);
            width:46px;
          }
          .door-callout.top i{
            left:50%;
            top:calc(100% + 4px);
            transform:rotate(48deg);
            transform-origin:left;
          }
          .door-callout.bottom i{
            left:50%;
            bottom:calc(100% + 4px);
            transform:rotate(-48deg);
            transform-origin:left;
          }
          .trunk-callout i{right:100%;top:50%;width:30px}

          .status-dock{
            display:grid;
            grid-template-columns:repeat(4,minmax(0,1fr));
            gap:10px;
            margin-top:12px;
          }
          .status-tile{
            min-width:0;
            min-height:86px;
            display:grid;
            grid-template-columns:44px minmax(0,1fr);
            align-items:center;
            gap:10px;
            padding:12px;
            border-radius:17px;
            background:linear-gradient(180deg,rgba(24,37,48,.99),rgba(11,20,28,.99));
            border:1px solid rgba(255,255,255,.10);
            box-shadow:inset 0 1px rgba(255,255,255,.02);
          }
          .status-icon{
            display:grid;
            place-items:center;
            width:44px;
            height:44px;
            border-radius:12px;
            background:rgba(255,255,255,.04);
          }
          .status-icon ha-icon{--mdc-icon-size:27px;color:#b9c4cb}
          .status-copy{
            min-width:0;
            display:flex;
            flex-direction:column;
            gap:5px;
            justify-content:center;
          }
          .status-copy small{
            font-size:12px;
            line-height:1.1;
            color:#b7c0c7;
          }
          .status-copy strong{
            display:block;
            font-size:15px;
            line-height:1.15;
            color:#f1f5f7;
            white-space:normal;
            overflow:visible;
            text-overflow:clip;
            word-break:break-word;
          }
          .status-tile.engine ha-icon,.status-tile.engine strong{color:var(--gwm-orange)}
          .status-tile.climate ha-icon,.status-tile.climate strong{color:var(--gwm-blue)}
          .status-tile.warn ha-icon,.status-tile.warn strong{color:var(--gwm-red)}
          .status-tile.lock ha-icon,.status-tile.lock strong{color:var(--gwm-green)}
          .status-tile.unlock ha-icon,.status-tile.unlock strong{color:var(--gwm-yellow)}

          .info-grid{
            display:grid;
            grid-template-columns:repeat(4,minmax(0,1fr));
            gap:8px;
            margin-top:10px;
          }
          .info-tile{
            display:flex;
            align-items:center;
            gap:8px;
            min-width:0;
            padding:10px 11px;
            border-radius:14px;
            background:rgba(255,255,255,.035);
            border:1px solid rgba(255,255,255,.06);
          }
          .info-tile ha-icon{--mdc-icon-size:21px;color:var(--gwm-blue)}
          .info-tile small{display:block;font-size:10px;color:#8e9ba5}
          .info-tile strong{display:block;margin-top:2px;font-size:12px;color:#e9eef2;white-space:normal}

          .remote-controls{
            display:grid;
            grid-template-columns:repeat(auto-fit,minmax(78px,1fr));
            gap:12px 8px;
            margin-top:14px;
            padding:16px 4px 4px;
            border-top:1px solid rgba(255,255,255,.08);
          }
          .remote-action{
            appearance:none;
            border:0;
            background:transparent;
            color:#e4ebef;
            display:flex;
            flex-direction:column;
            align-items:center;
            gap:8px;
            min-width:0;
            cursor:pointer;
            font:inherit;
          }
          .remote-action>span:last-child{
            width:100%;
            min-height:26px;
            font-size:11px;
            line-height:1.15;
            white-space:normal;
            text-align:center;
          }
          .action-circle{
            width:60px;
            height:60px;
            border-radius:50%;
            display:grid;
            place-items:center;
            background:linear-gradient(180deg,#1a2b38,#0f1b24);
            border:1px solid rgba(255,255,255,.12);
            box-shadow:0 5px 15px rgba(0,0,0,.20);
          }
          .action-circle ha-icon{--mdc-icon-size:29px;color:var(--gwm-blue)}
          .remote-action.active .action-circle ha-icon{color:var(--gwm-orange)}
          .remote-action.warn .action-circle ha-icon{color:var(--gwm-red)}
          .remote-action.experimental .action-circle{border-style:dashed}
          .remote-action.busy,.remote-action:disabled{opacity:.45}
          .remote-action:disabled{pointer-events:none}

          @keyframes enginePulse{0%,100%{opacity:.45}50%{opacity:1}}
          @keyframes engineIconPulse{0%,100%{stroke-width:4.5}50%{stroke-width:6}}
          @keyframes fanSpin{to{transform:rotate(360deg)}}
          @keyframes airflow{to{stroke-dashoffset:-60}}
          @keyframes windowPulse{0%,100%{opacity:.5}50%{opacity:1}}
          @keyframes unknownDoorPulse{0%,100%{opacity:.45}50%{opacity:1}}

          @container (max-width:620px){
            .hero{min-height:430px}
            .brand{left:16px;top:15px}
            .brand strong{font-size:27px}
            .brand span{font-size:11px;letter-spacing:5px;margin-top:6px}
            .vehicle-name{top:20px;font-size:13px;max-width:38%}
            .connection-card{right:10px;top:10px;min-width:132px;padding:9px 10px}
            .online-line{font-size:11px}
            .gsm-line{font-size:9px;margin-top:7px}
            .car-scene{top:62px}
            .jolion-scene{left:-1%;width:102%}
            .door-callout span,.door-callout strong,.trunk-callout span,.trunk-callout strong{font-size:10px}
            .door-callout{min-width:96px}
            .trunk-callout{left:91%;min-width:66px}
            .status-dock{grid-template-columns:repeat(4,minmax(0,1fr));gap:7px}
            .status-tile{
              min-height:78px;
              grid-template-columns:36px minmax(0,1fr);
              gap:7px;
              padding:9px;
              border-radius:14px;
            }
            .status-icon{width:36px;height:36px;border-radius:10px}
            .status-icon ha-icon{--mdc-icon-size:22px}
            .status-copy small{font-size:10px}
            .status-copy strong{font-size:12px}
            .info-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
            .action-circle{width:56px;height:56px}
            .remote-action>span:last-child{font-size:10px}
          }

          @container (max-width:420px){
            .hero{min-height:400px}
            .status-dock{grid-template-columns:repeat(2,minmax(0,1fr))}
            .status-copy small{font-size:11px}
            .status-copy strong{font-size:13px}
            .remote-controls{grid-template-columns:repeat(3,minmax(0,1fr))}
          }
        </style>

        <ha-card>
          <div class="wrap">
            <div class="hero">
              <div class="brand"><strong>GWM</strong><span>JOLION</span></div>
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

      this.shadowRoot.querySelectorAll("[data-action]").forEach((button) =>
        button.addEventListener("click", () => this._handleAction(button.dataset.action)),
      );
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
          if (blockers.length) return alert(`GWM Jolion: запуск недоступен — ${blockers.join(", ")}.`);
        }
        if (!this._confirm(engine ? "Остановить двигатель?" : "Запустить двигатель на 15 минут?")) return;
        return this._runBusy(action, () =>
          this._hass.callService(INTEGRATION, engine ? "stop_engine" : "start_engine", engine ? {} : { operation_time: 15 }),
        );
      }

      if (action === "climate") {
        const entityId = this._entities.climate;
        if (!entityId) return alert("GWM Jolion: сущность климата не найдена");
        if (!this._confirm(climate ? "Выключить климат?" : "Включить климат? На автомобиле с ДВС может запуститься двигатель.")) return;
        return this._runBusy(action, () =>
          this._hass.callService("climate", climate ? "turn_off" : "turn_on", { entity_id: entityId }),
        );
      }

      if (action === "trunk") {
        if (!this._confirm(trunk ? "Закрыть багажник?" : "Открыть багажник?")) return;
        return this._runBusy(action, () =>
          this._hass.callService(INTEGRATION, trunk ? "close_trunk" : "open_trunk", {}),
        );
      }

      if (action === "windows") {
        if (!this._confirm(windows ? "Закрыть все окна?" : "Открыть все окна? Команда открытия экспериментальная.")) return;
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
        return this._toggleRoof(action, "sunroofOpen", "open_sunroof", "close_sunroof", "панораму");
      }

      if (action === "sunshade") {
        return this._toggleRoof(action, "sunshadeOpen", "open_sunshade", "close_sunshade", "шторку");
      }
    }

    async _toggleComfort(action, key, onService, offService, label) {
      const current = !this._isUnavailable(key) ? this._isOn(key) : Boolean(this._assumed[key]);
      const next = !current;
      if (!this._confirm(`${next ? "Включить" : "Выключить"} ${label}?`)) return;
      return this._runBusy(
        action,
        () => this._hass.callService(INTEGRATION, next ? onService : offService, {}),
        () => { this._assumed[key] = next; },
      );
    }

    async _toggleRoof(action, key, openService, closeService, label) {
      let current = this._assumed[key];
      if (current === undefined) {
        const open = window.confirm(`${label[0].toUpperCase()}${label.slice(1)}: ОК — открыть, Отмена — закрыть.`);
        current = !open;
      }
      const next = !current;
      if (this._config.confirm_controls !== false && !this._confirm(`${next ? "Открыть" : "Закрыть"} ${label}?`)) return;
      return this._runBusy(
        action,
        () => this._hass.callService(INTEGRATION, next ? openService : closeService, {}),
        () => { this._assumed[key] = next; },
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
      description: "Широкий top-view Jolion с крупными статусами, значениями топлива/пробега и независимой анимацией дверей, багажника, двигателя и климата",
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
