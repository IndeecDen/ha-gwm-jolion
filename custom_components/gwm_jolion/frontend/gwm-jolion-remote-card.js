/* GWM Jolion Remote Card v0.1.0-alpha.13 */
(() => {
  const CARD_VERSION = "0.1.0-alpha.13";
  const INTEGRATION = "gwm_jolion";

  const DEFAULT_CONTROLS = ["lock", "engine", "climate"];
  const DEFAULT_INFO = ["fuel", "range", "mileage", "tires"];
  const DEFAULT_STATUSES = ["lock", "engine", "doors", "windows", "trunk", "climate"];

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
    ["seat_driver", "Подогрев сиденья водителя"],
    ["seat_passenger", "Подогрев сиденья пассажира"],
  ];

  const STATUS_OPTIONS = [
    ["lock", "Замок"],
    ["engine", "Двигатель"],
    ["doors", "Двери"],
    ["windows", "Окна"],
    ["trunk", "Багажник"],
    ["climate", "Климат"],
    ["online", "T-Box online"],
    ["gps", "GPS"],
  ];

  const SUFFIX = {
    engine: "_engine_running",
    doors: "_doors_open",
    windows: "_windows_open",
    windowFl: "_window_2210002_open",
    windowFr: "_window_2210001_open",
    windowRl: "_window_2210004_open",
    windowRr: "_window_2210003_open",
    trunk: "_trunk_open",
    unlocked: "_vehicle_unlocked",
    climateOn: "_climate_on",
    tbox: "_tbox_online",
    gps: "_gps_authorized",
    lock: "_central_lock",
    climate: "_climate",
    climateRuntime: "_climate_runtime",
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
    seatDriver: "_driver_seat_heat_level_raw",
    seatPassenger: "_passenger_seat_heat_level_raw",
  };

  const FEATURE_BY_CONTROL = {
    steering: "steering_wheel_heat",
    rear_defrost: "rear_defrost",
    front_defrost: "front_defrost",
    sunroof: "sunroof",
    sunshade: "sunshade",
  };

  const FEATURE_BY_INFO = {
    seat_driver: "seat_heat_driver",
    seat_passenger: "seat_heat_passenger",
  };

  class GwmJolionRemoteCardEditor extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: "open" });
      this._config = {};
      this._hass = null;
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
        car_color: "#7c8489",
        ...config,
      };
      this._render();
    }

    _toggleList(key, value, checked) {
      const current = Array.isArray(this._config[key]) ? [...this._config[key]] : [];
      const next = checked
        ? current.includes(value) ? current : [...current, value]
        : current.filter((item) => item !== value);
      this._emit({ ...this._config, [key]: next });
    }

    _emit(config) {
      this._config = config;
      this.dispatchEvent(
        new CustomEvent("config-changed", {
          detail: { config },
          bubbles: true,
          composed: true,
        })
      );
      this._render();
    }

    _renderGroup(title, key, options) {
      const selected = Array.isArray(this._config[key]) ? this._config[key] : [];
      return `
        <section>
          <h4>${title}</h4>
          <div class="grid">
            ${options.map(([value, label]) => `
              <label class="check">
                <input type="checkbox" data-list="${key}" data-value="${value}" ${selected.includes(value) ? "checked" : ""}>
                <span>${label}</span>
              </label>
            `).join("")}
          </div>
        </section>`;
    }

    _render() {
      if (!this.shadowRoot) return;
      const title = this._config.title || "";
      const carColor = /^#[0-9a-f]{6}$/i.test(this._config.car_color || "")
        ? this._config.car_color
        : "#7c8489";
      this.shadowRoot.innerHTML = `
        <style>
          :host { display:block; }
          .editor { display:grid; gap:16px; padding:4px 0 12px; }
          section { display:grid; gap:8px; }
          h4 { margin:0; font-size:14px; color:var(--primary-text-color); }
          .field-row { display:grid; grid-template-columns:minmax(0,1fr) auto; gap:12px; align-items:end; }
          label.field { display:grid; gap:6px; color:var(--secondary-text-color); font-size:12px; }
          input[type="text"] {
            width:100%; min-height:40px; border-radius:8px; padding:0 10px;
            border:1px solid var(--divider-color); background:var(--card-background-color);
            color:var(--primary-text-color); font:inherit;
          }
          input[type="color"] { width:48px; height:40px; padding:2px; border:0; background:transparent; }
          .grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:7px 14px; }
          .check { display:flex; align-items:center; gap:8px; min-height:30px; font-size:13px; color:var(--primary-text-color); }
          .note { padding:10px 12px; border-radius:10px; background:color-mix(in srgb,var(--primary-color) 7%,transparent); color:var(--secondary-text-color); font-size:12px; line-height:1.4; }
          @media (max-width:520px) { .grid { grid-template-columns:1fr; } }
        </style>
        <div class="editor">
          <div class="field-row">
            <label class="field">
              Название карточки (необязательно)
              <input id="title" type="text" value="${this._escape(title)}" placeholder="Haval Jolion">
            </label>
            <label class="field">
              Цвет автомобиля
              <input id="car-color" type="color" value="${carColor}">
            </label>
          </div>
          <label class="check">
            <input id="confirm-controls" type="checkbox" ${this._config.confirm_controls !== false ? "checked" : ""}>
            <span>Подтверждать удалённые команды</span>
          </label>
          ${this._renderGroup("Кнопки управления", "controls", CONTROL_OPTIONS)}
          ${this._renderGroup("Информация под автомобилем", "info", INFO_OPTIONS)}
          ${this._renderGroup("Статусы вокруг автомобиля", "statuses", STATUS_OPTIONS)}
          <div class="note">Настройки оборудования самой интеграции имеют приоритет. Если функция отмечена как отсутствующая в GWM Jolion → Настроить, эта карточка её не покажет даже при выбранном флажке.</div>
        </div>`;

      this.shadowRoot.querySelectorAll("[data-list]").forEach((input) => {
        input.addEventListener("change", () =>
          this._toggleList(input.dataset.list, input.dataset.value, input.checked)
        );
      });
      this.shadowRoot.getElementById("confirm-controls")?.addEventListener("change", (event) => {
        this._emit({ ...this._config, confirm_controls: event.target.checked });
      });
      this.shadowRoot.getElementById("title")?.addEventListener("change", (event) => {
        const value = String(event.target.value || "").trim();
        const next = { ...this._config };
        if (value) next.title = value;
        else delete next.title;
        this._emit(next);
      });
      this.shadowRoot.getElementById("car-color")?.addEventListener("change", (event) => {
        this._emit({ ...this._config, car_color: event.target.value });
      });
    }

    _escape(value) {
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }
  }

  class GwmJolionRemoteCard extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: "open" });
      this._config = {};
      this._hass = null;
      this._entityRegistry = [];
      this._device = null;
      this._entities = {};
      this._resolvedKey = null;
      this._resolving = false;
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
      return { columns: 12, rows: 9, min_columns: 6, min_rows: 6 };
    }

    setConfig(config) {
      this._config = {
        controls: [...DEFAULT_CONTROLS],
        info: [...DEFAULT_INFO],
        statuses: [...DEFAULT_STATUSES],
        confirm_controls: true,
        car_color: "#7c8489",
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
      return 9;
    }

    async _resolveEntities() {
      if (!this._hass || this._resolving) return;
      this._resolving = true;
      try {
        const registry = await this._hass.callWS({ type: "config/entity_registry/list" });
        this._entityRegistry = Array.isArray(registry) ? registry : [];

        let deviceId = this._config.device_id || null;
        if (!deviceId && this._config.entity) {
          deviceId = this._entityRegistry.find((entry) => entry.entity_id === this._config.entity)?.device_id || null;
        }

        const gwmEntries = this._entityRegistry.filter((entry) =>
          entry.platform === INTEGRATION || this._isGwmUniqueId(entry.unique_id)
        );
        if (!deviceId) deviceId = gwmEntries.find((entry) => entry.device_id)?.device_id || null;
        const vehicleEntries = deviceId
          ? gwmEntries.filter((entry) => entry.device_id === deviceId)
          : gwmEntries;

        const devices = await this._hass.callWS({ type: "config/device_registry/list" });
        this._device = Array.isArray(devices)
          ? devices.find((device) => device.id === deviceId) || null
          : null;

        this._entities = {};
        for (const [key, suffix] of Object.entries(SUFFIX)) {
          const found = vehicleEntries.find((entry) => String(entry.unique_id || "").endsWith(suffix));
          if (found) this._entities[key] = found.entity_id;
        }
        this._entities.climate ||= vehicleEntries.find((entry) => entry.entity_id.startsWith("climate."))?.entity_id;
        this._entities.lock ||= vehicleEntries.find((entry) => entry.entity_id.startsWith("lock."))?.entity_id;
        this._entities.refresh ||= vehicleEntries.find((entry) => entry.entity_id.startsWith("button.") && /refresh|obnov/i.test(entry.entity_id))?.entity_id;

        this._resolvedKey = `${this._config.device_id || ""}|${this._config.entity || ""}`;
      } catch (err) {
        console.error("[GWM Jolion Remote Card] entity discovery failed", err);
      } finally {
        this._resolving = false;
        this._render();
      }
    }

    _isGwmUniqueId(uniqueId) {
      if (!uniqueId) return false;
      return Object.values(SUFFIX).some((suffix) => String(uniqueId).endsWith(suffix));
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

    _value(key, fallback = "—") {
      const stateObj = this._state(key);
      if (!stateObj || ["unknown", "unavailable", ""].includes(stateObj.state)) return fallback;
      const unit = stateObj.attributes?.unit_of_measurement;
      return `${stateObj.state}${unit ? ` ${unit}` : ""}`;
    }

    _rawValue(key) {
      const stateObj = this._state(key);
      if (!stateObj || ["unknown", "unavailable", ""].includes(stateObj.state)) return null;
      return String(stateObj.state);
    }

    _featureEnabled(capability) {
      const flags = this._state("featureFlags");
      if (!flags?.attributes || !(capability in flags.attributes)) return true;
      return flags.attributes[capability] !== false;
    }

    _remoteCommandInProgress() {
      const state = this._state("lastCommand");
      return state?.attributes?.in_progress === true;
    }

    _drivetrain() {
      if (this._config.drivetrain) return String(this._config.drivetrain).toUpperCase();
      const raw = (this._rawValue("modelCode") || "").toUpperCase();
      if (raw.includes("CC7150BA24C")) return "4WD";
      if (raw.includes("CC7150BA00B") || raw.includes("CC7150BA01B")) return "2WD";
      return null;
    }

    _headerTitle() {
      if (this._config.title) return String(this._config.title);
      const model = String(this._device?.model || "Haval Jolion").trim();
      const apiName = String(this._device?.name || "").trim();
      const drivetrain = this._drivetrain();
      const parts = [model];
      if (apiName && apiName.toLocaleLowerCase() !== model.toLocaleLowerCase() && apiName.toLocaleLowerCase() !== "gwm jolion") parts.push(apiName);
      if (drivetrain) parts.push(drivetrain);
      return parts.join(" ");
    }

    _openWindows() {
      const definitions = [
        ["windowFl", "ПЛ"], ["windowFr", "ПП"], ["windowRl", "ЗЛ"], ["windowRr", "ЗП"],
      ];
      return definitions.filter(([key]) => !this._isUnavailable(key) && this._isOn(key)).map(([, label]) => label);
    }

    _relativeUpdate() {
      const raw = this._rawValue("lastUpdate");
      if (!raw) return "Нет данных";
      const then = new Date(raw).getTime();
      if (!Number.isFinite(then)) return "Нет данных";
      const seconds = Math.max(0, Math.round((Date.now() - then) / 1000));
      if (seconds < 15) return "только что";
      if (seconds < 60) return `${seconds} сек назад`;
      const minutes = Math.floor(seconds / 60);
      if (minutes < 60) return `${minutes} мин назад`;
      const hours = Math.floor(minutes / 60);
      if (hours < 24) return `${hours} ч назад`;
      return `${Math.floor(hours / 24)} дн назад`;
    }

    _safeColor() {
      return /^#[0-9a-f]{6}$/i.test(this._config.car_color || "") ? this._config.car_color : "#7c8489";
    }

    _escape(value) {
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }

    _icon(icon) {
      return `<ha-icon icon="${icon}"></ha-icon>`;
    }

    _carSvg() {
      const engineOn = this._isOn("engine");
      const doorsOpen = this._isOn("doors");
      const trunkOpen = this._isOn("trunk");
      const windowsOpen = this._isOn("windows");
      return `
        <svg class="jolion" viewBox="0 0 520 245" role="img" aria-label="Haval Jolion">
          <defs>
            <linearGradient id="bodyShade" x1="0" x2="1" y1="0" y2="1">
              <stop offset="0" stop-color="var(--gwm-car-color)" stop-opacity="1"/>
              <stop offset="1" stop-color="var(--gwm-car-color)" stop-opacity=".68"/>
            </linearGradient>
            <linearGradient id="glass" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0" stop-color="#4b5863"/>
              <stop offset="1" stop-color="#202a32"/>
            </linearGradient>
            <filter id="glow"><feGaussianBlur stdDeviation="5" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
          </defs>
          <ellipse cx="278" cy="215" rx="190" ry="18" class="shadow"/>
          ${engineOn ? '<ellipse cx="275" cy="205" rx="175" ry="12" class="engine-glow"/>' : ''}
          <g class="car-shape">
            <path class="body" d="M75 165 L92 130 Q101 112 126 104 L206 84 Q226 60 263 51 L345 50 Q369 52 388 68 L429 105 Q448 112 458 132 L468 166 Q464 185 443 190 L111 190 Q85 187 75 165Z"/>
            <path class="hood" d="M93 129 Q112 111 138 105 L216 86 L241 108 L147 123 Z"/>
            <path class="side-line" d="M151 126 Q263 112 420 118"/>
            <path class="roof-line" d="M207 84 Q230 58 264 51 L345 51 Q367 54 385 68 L420 105"/>
            <path class="glass wind" d="M218 84 Q237 63 266 58 L300 58 L303 103 L242 105 Z"/>
            <path class="glass side" d="M309 58 L344 58 Q360 61 375 74 L408 104 L312 103 Z"/>
            <path class="window-divider" d="M306 60 L308 104"/>
            <path class="door-line ${doorsOpen ? 'warn-line' : ''}" d="M246 108 L253 182 M349 107 L358 183"/>
            <path class="rear-hatch ${trunkOpen ? 'warn-line' : ''}" d="M419 111 Q443 125 451 161"/>
            <path class="front-face" d="M76 160 L88 134 Q95 118 113 112 L142 108 L154 139 L145 179 L93 179 Z"/>
            <path class="grille" d="M82 151 L91 131 L120 122 L145 126 L148 166 L137 177 L91 175 Z"/>
            <g class="grille-bars">
              <path d="M91 136 L140 134"/><path d="M88 145 L143 143"/><path d="M86 154 L145 152"/><path d="M86 163 L143 161"/>
              <path d="M100 129 L98 171"/><path d="M114 126 L113 173"/><path d="M128 126 L128 171"/>
            </g>
            <text class="haval-badge" x="111" y="151" text-anchor="middle">HAVAL</text>
            <path class="headlight" d="M142 119 L193 109 L209 116 L193 127 L151 132 Z"/>
            <path class="drl" d="M151 132 L147 158"/>
            <path class="far-headlight" d="M95 117 L127 110 L137 115 L128 123 L101 126 Z"/>
            <path class="bumper" d="M82 171 Q110 183 149 175"/>
            <path class="sill" d="M149 183 L419 184"/>
            <path class="mirror" d="M225 101 Q214 99 207 107 L226 111 Z"/>
            <path class="window-alert ${windowsOpen ? 'warn-window' : ''}" d="M244 108 L302 106 L302 121 L246 125 Z"/>
            <g class="wheel front-wheel" transform="translate(164 184)">
              <circle r="35" class="tire"/><circle r="21" class="rim"/><circle r="7" class="hub"/>
              <path d="M0 -16 V16 M-16 0 H16 M-11 -11 L11 11 M11 -11 L-11 11" class="spokes"/>
            </g>
            <g class="wheel rear-wheel" transform="translate(390 184)">
              <circle r="35" class="tire"/><circle r="21" class="rim"/><circle r="7" class="hub"/>
              <path d="M0 -16 V16 M-16 0 H16 M-11 -11 L11 11 M11 -11 L-11 11" class="spokes"/>
            </g>
          </g>
        </svg>`;
    }

    _statusMeta(id) {
      const unknown = (key) => this._isUnavailable(key);
      const noData = (label, position, icon = "mdi:help-circle-outline") =>
        [icon, `${label}: нет данных`, "muted", position];
      const unlocked = this._isOn("unlocked");
      const engine = this._isOn("engine");
      const doors = this._isOn("doors");
      const windows = this._isOn("windows");
      const trunk = this._isOn("trunk");
      const climateKnown = !unknown("climateOn") || !unknown("climate");
      const climate = this._isOn("climateOn") || this._state("climate")?.state === "heat_cool";
      const online = this._isOn("tbox");
      const gps = this._isOn("gps");
      return {
        lock: unknown("unlocked") ? noData("Замок", "s-lock", "mdi:lock-question") : [unlocked ? "mdi:lock-open-variant" : "mdi:lock", unlocked ? "Открыт" : "Закрыт", unlocked ? "warn" : "ok", "s-lock"],
        engine: unknown("engine") ? noData("Двигатель", "s-engine", "mdi:engine-outline") : ["mdi:engine", engine ? "Двигатель работает" : "Двигатель выключен", engine ? "active" : "muted", "s-engine"],
        doors: unknown("doors") ? noData("Двери", "s-doors", "mdi:car-door") : [doors ? "mdi:car-door-open" : "mdi:car-door", doors ? "Дверь открыта" : "Двери закрыты", doors ? "warn" : "ok", "s-doors"],
        windows: unknown("windows") ? noData("Окна", "s-windows", "mdi:car-door") : ["mdi:car-door", windows ? `Окна: ${this._openWindows().join(", ") || "открыты"}` : "Окна закрыты", windows ? "warn" : "ok", "s-windows"],
        trunk: unknown("trunk") ? noData("Багажник", "s-trunk", "mdi:car-back") : ["mdi:car-back", trunk ? "Багажник открыт" : "Багажник закрыт", trunk ? "warn" : "ok", "s-trunk"],
        climate: !climateKnown ? noData("Климат", "s-climate", "mdi:air-conditioner") : ["mdi:air-conditioner", climate ? "Климат работает" : "Климат выключен", climate ? "active" : "muted", "s-climate"],
        online: unknown("tbox") ? noData("T-Box", "s-online", "mdi:cloud-question") : [online ? "mdi:cloud-check" : "mdi:cloud-off-outline", online ? "T-Box online" : "T-Box offline", online ? "ok" : "warn", "s-online"],
        gps: unknown("gps") ? noData("GPS", "s-gps", "mdi:crosshairs-question") : ["mdi:crosshairs-gps", gps ? "GPS доступен" : "GPS недоступен", gps ? "ok" : "muted", "s-gps"],
      }[id];
    }

    _renderStatuses() {
      const selected = Array.isArray(this._config.statuses) ? this._config.statuses : DEFAULT_STATUSES;
      return selected.map((id) => {
        const meta = this._statusMeta(id);
        if (!meta) return "";
        const [icon, label, tone, position] = meta;
        return `<div class="vehicle-status ${position} ${tone}" title="${this._escape(label)}">${this._icon(icon)}<span>${this._escape(label)}</span></div>`;
      }).join("");
    }

    _infoMeta(id) {
      if (FEATURE_BY_INFO[id] && !this._featureEnabled(FEATURE_BY_INFO[id])) return null;
      const climate = this._state("climate");
      const climateOn = this._isOn("climateOn") || climate?.state === "heat_cool";
      const pressureValues = ["tireFlP", "tireFrP", "tireRlP", "tireRrP"].map((key) => this._rawValue(key)).filter(Boolean);
      const seatValue = (key) => {
        const raw = this._rawValue(key);
        if (raw === null) return "—";
        const n = Number(raw);
        return Number.isFinite(n) ? (n === 0 ? "выкл" : `ур. ${n}`) : raw;
      };
      return {
        fuel: ["mdi:fuel", "Топливо", `${this._value("fuel")} · ${this._value("fuelPercent")}`],
        range: ["mdi:map-marker-distance", "Запас хода", this._value("range")],
        mileage: ["mdi:counter", "Пробег", this._value("mileage")],
        tires: ["mdi:car-tire-alert", "Шины", pressureValues.length ? `${pressureValues.join(" / ")} bar` : "—"],
        gsm: ["mdi:signal", "GSM / T-Box", this._isOn("tbox") ? `online · ${this._rawValue("signal") ?? "—"}/4` : "offline"],
        gps: ["mdi:crosshairs-gps", "GPS", this._isOn("gps") ? "доступен" : "нет"],
        climate: ["mdi:air-conditioner", "Климат", climateOn ? `работает · ${climate?.attributes?.temperature ?? 22} °C` : "выключен"],
        oil: ["mdi:oil", "Масло GWM", this._rawValue("oilQty") === null ? "—" : `${this._rawValue("oilQty")}/8`],
        update: ["mdi:cloud-sync", "Обновление", this._relativeUpdate()],
        seat_driver: ["mdi:car-seat-heater", "Сиденье водителя", seatValue("seatDriver")],
        seat_passenger: ["mdi:car-seat-heater", "Сиденье пассажира", seatValue("seatPassenger")],
      }[id] || null;
    }

    _renderInfo() {
      const selected = Array.isArray(this._config.info) ? this._config.info : DEFAULT_INFO;
      const tiles = selected.map((id) => {
        const meta = this._infoMeta(id);
        if (!meta) return "";
        const [icon, label, value] = meta;
        return `<div class="info-tile">${this._icon(icon)}<div><small>${this._escape(label)}</small><strong>${this._escape(value)}</strong></div></div>`;
      }).filter(Boolean);
      return tiles.length ? `<div class="info-grid">${tiles.join("")}</div>` : "";
    }

    _controlMeta(id) {
      const feature = FEATURE_BY_CONTROL[id];
      if (feature && !this._featureEnabled(feature)) return null;
      const unlockedKnown = !this._isUnavailable("unlocked");
      const engineKnown = !this._isUnavailable("engine");
      const climateKnown = !this._isUnavailable("climateOn") || !this._isUnavailable("climate");
      const trunkKnown = !this._isUnavailable("trunk");
      const windowsKnown = !this._isUnavailable("windows");
      const unlocked = this._isOn("unlocked");
      const engine = this._isOn("engine");
      const climate = this._isOn("climateOn") || this._state("climate")?.state === "heat_cool";
      const trunk = this._isOn("trunk");
      const windows = this._isOn("windows");
      const steering = !this._isUnavailable("steeringHeat") ? this._isOn("steeringHeat") : Boolean(this._assumed.steeringHeat);
      const rearDefrost = !this._isUnavailable("rearDefrost") ? this._isOn("rearDefrost") : Boolean(this._assumed.rearDefrost);
      const frontDefrost = !this._isUnavailable("frontDefrost") ? this._isOn("frontDefrost") : Boolean(this._assumed.frontDefrost);
      return {
        lock: unlockedKnown ? [unlocked ? "mdi:lock" : "mdi:lock-open-variant", unlocked ? "Закрыть" : "Открыть", unlocked ? "active" : "", false] : ["mdi:lock-question", "Замок · нет данных", "", true],
        engine: engineKnown ? [engine ? "mdi:engine-off" : "mdi:engine", engine ? "Заглушить" : "Запустить", engine ? "active" : "", false] : ["mdi:engine-outline", "Двигатель · нет данных", "", true],
        climate: climateKnown ? ["mdi:air-conditioner", climate ? "Климат выкл." : "Климат вкл.", climate ? "active" : "", false] : ["mdi:air-conditioner", "Климат · нет данных", "", true],
        trunk: trunkKnown ? ["mdi:car-back", trunk ? "Закрыть багажник" : "Открыть багажник", trunk ? "warn" : "", false] : ["mdi:car-back", "Багажник · нет данных", "", true],
        windows: windowsKnown ? ["mdi:car-door", windows ? "Закрыть окна" : "Открыть окна", windows ? "warn" : "", false] : ["mdi:car-door", "Окна · нет данных", "", true],
        refresh: ["mdi:refresh", "Обновить", "", false],
        steering: ["mdi:steering", steering ? "Руль выкл." : "Руль вкл.", steering ? "active" : "", false],
        rear_defrost: ["mdi:car-defrost-rear", rearDefrost ? "Заднее стекло выкл." : "Заднее стекло вкл.", rearDefrost ? "active" : "", false],
        front_defrost: ["mdi:car-defrost-front", frontDefrost ? "Defrost выкл." : "Defrost вкл.", frontDefrost ? "active" : "experimental", false],
        sunroof: ["mdi:car-select", "Панорама", "experimental", false],
        sunshade: ["mdi:blinds", "Шторка", "experimental", false],
      }[id] || null;
    }

    _renderControls() {
      const selected = Array.isArray(this._config.controls) ? this._config.controls : DEFAULT_CONTROLS;
      const controls = selected.map((id) => {
        const meta = this._controlMeta(id);
        if (!meta) return "";
        const [icon, label, tone, disabled = false] = meta;
        const busy = this._busy.has(id) || (id !== "refresh" && this._remoteCommandInProgress());
        const blocked = disabled || busy;
        return `
          <button type="button" class="remote-action ${tone} ${busy ? "busy" : ""} ${disabled ? "disabled" : ""}" ${blocked ? "disabled" : `data-action="${id}"`}>
            <span class="action-circle">${this._icon(icon)}</span>
            <span>${this._escape(label)}</span>
          </button>`;
      }).filter(Boolean);
      return controls.length ? `<div class="remote-controls">${controls.join("")}</div>` : "";
    }

    _render() {
      if (!this.shadowRoot) return;
      if (!this._hass) {
        this.shadowRoot.innerHTML = `<ha-card><div style="padding:20px">GWM Jolion Remote Card</div></ha-card>`;
        return;
      }

      const onlineKnown = !this._isUnavailable("tbox");
      const online = onlineKnown && this._isOn("tbox");
      const carColor = this._safeColor();
      this.shadowRoot.innerHTML = `
        <style>
          :host { display:block; --gwm-car-color:${carColor}; }
          * { box-sizing:border-box; }
          ha-card { overflow:hidden; border-radius:var(--ha-card-border-radius,20px); background:var(--ha-card-background,var(--card-background-color)); }
          .wrap { position:relative; padding:18px; color:var(--primary-text-color); }
          .header { display:flex; align-items:center; justify-content:space-between; gap:10px; margin-bottom:4px; }
          .header h2 { margin:0; min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:20px; line-height:1.2; }
          .connection { display:flex; align-items:center; gap:6px; color:var(--secondary-text-color); font-size:11px; white-space:nowrap; }
          .connection i { width:8px; height:8px; border-radius:50%; background:var(--error-color,#d32f2f); box-shadow:0 0 0 4px color-mix(in srgb,var(--error-color,#d32f2f) 11%,transparent); }
          .connection.online i { background:var(--success-color,#43a047); box-shadow:0 0 0 4px color-mix(in srgb,var(--success-color,#43a047) 11%,transparent); }
          .connection.unknown i { background:var(--secondary-text-color); box-shadow:none; }
          .stage { position:relative; min-height:265px; margin-top:6px; border-radius:18px; background:radial-gradient(circle at 50% 42%,color-mix(in srgb,var(--primary-color) 10%,transparent),transparent 58%); overflow:hidden; }
          .jolion { position:absolute; width:min(86%,500px); height:auto; left:50%; top:50%; transform:translate(-50%,-46%); overflow:visible; }
          .shadow { fill:rgba(0,0,0,.18); }
          .engine-glow { fill:color-mix(in srgb,var(--warning-color,#f9a825) 28%,transparent); filter:url(#glow); }
          .body { fill:url(#bodyShade); stroke:color-mix(in srgb,var(--primary-text-color) 45%,transparent); stroke-width:2.2; }
          .hood,.front-face { fill:color-mix(in srgb,var(--gwm-car-color) 82%,white 18%); stroke:color-mix(in srgb,var(--primary-text-color) 38%,transparent); stroke-width:1.6; }
          .glass { fill:url(#glass); stroke:rgba(255,255,255,.24); stroke-width:1.2; }
          .roof-line,.side-line,.door-line,.rear-hatch,.sill,.bumper,.window-divider { fill:none; stroke:color-mix(in srgb,var(--primary-text-color) 34%,transparent); stroke-width:1.4; }
          .warn-line { stroke:var(--error-color,#d32f2f); stroke-width:2.4; }
          .grille { fill:#171b1e; stroke:#555f66; stroke-width:1.2; }
          .grille-bars path { fill:none; stroke:#788188; stroke-width:1; opacity:.9; }
          .haval-badge { fill:#e6e7e8; font-size:7.5px; font-family:Arial,sans-serif; font-weight:700; letter-spacing:.7px; }
          .headlight,.far-headlight { fill:#e9f5ff; stroke:#c8eaff; stroke-width:1.1; filter:${this._isOn("engine") ? "url(#glow)" : "none"}; }
          .drl { fill:none; stroke:#f8fbff; stroke-width:3; stroke-linecap:round; }
          .mirror { fill:color-mix(in srgb,var(--gwm-car-color) 72%,black 28%); }
          .window-alert { fill:transparent; }
          .warn-window { fill:color-mix(in srgb,var(--error-color,#d32f2f) 20%,transparent); stroke:var(--error-color,#d32f2f); stroke-width:1.4; }
          .tire { fill:#181a1c; stroke:#3b4146; stroke-width:2; }
          .rim { fill:#a7adb1; stroke:#51585d; stroke-width:2; }
          .hub { fill:#525a5f; }
          .spokes { fill:none; stroke:#5f686e; stroke-width:2.4; }
          .vehicle-status { position:absolute; display:flex; align-items:center; gap:6px; max-width:150px; padding:7px 9px; border-radius:999px; background:color-mix(in srgb,var(--card-background-color) 84%,transparent); border:1px solid color-mix(in srgb,var(--divider-color) 75%,transparent); box-shadow:0 4px 18px rgba(0,0,0,.08); backdrop-filter:blur(8px); font-size:10px; color:var(--secondary-text-color); z-index:2; }
          .vehicle-status ha-icon { --mdc-icon-size:18px; flex:none; }
          .vehicle-status span { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
          .vehicle-status.ok ha-icon { color:var(--success-color,#43a047); }
          .vehicle-status.warn ha-icon { color:var(--error-color,#d32f2f); }
          .vehicle-status.active ha-icon { color:var(--warning-color,#f9a825); }
          .vehicle-status.muted ha-icon { color:var(--secondary-text-color); }
          .s-lock { left:8px; top:12px; } .s-engine { right:8px; top:12px; }
          .s-doors { left:4px; top:92px; } .s-windows { right:4px; top:92px; }
          .s-trunk { left:12px; bottom:12px; } .s-climate { right:12px; bottom:12px; }
          .s-online { left:50%; top:8px; transform:translateX(-50%); } .s-gps { left:50%; bottom:8px; transform:translateX(-50%); }
          .info-grid { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:8px; margin-top:10px; }
          .info-tile { min-width:0; display:flex; align-items:center; gap:8px; padding:10px; border-radius:13px; background:color-mix(in srgb,var(--primary-color) 6%,transparent); }
          .info-tile ha-icon { --mdc-icon-size:20px; color:var(--primary-color); flex:none; }
          .info-tile div { min-width:0; }
          .info-tile small { display:block; color:var(--secondary-text-color); font-size:9.5px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
          .info-tile strong { display:block; margin-top:2px; font-size:11.5px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
          .remote-controls { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:10px; margin-top:16px; padding-top:14px; border-top:1px solid var(--divider-color); }
          .remote-action { appearance:none; border:0; background:transparent; color:var(--primary-text-color); display:flex; flex-direction:column; align-items:center; gap:7px; min-width:0; cursor:pointer; font:inherit; }
          .remote-action > span:last-child { width:100%; font-size:10.5px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; text-align:center; }
          .action-circle { width:58px; height:58px; display:grid; place-items:center; border-radius:50%; background:color-mix(in srgb,var(--primary-color) 9%,var(--card-background-color)); border:1px solid color-mix(in srgb,var(--primary-color) 14%,var(--divider-color)); box-shadow:0 5px 16px rgba(0,0,0,.08); transition:transform .12s ease,background .12s ease; }
          .action-circle ha-icon { --mdc-icon-size:27px; color:var(--primary-color); }
          .remote-action:hover .action-circle { background:color-mix(in srgb,var(--primary-color) 15%,var(--card-background-color)); }
          .remote-action:active .action-circle { transform:scale(.95); }
          .remote-action.active .action-circle { background:color-mix(in srgb,var(--warning-color,#f9a825) 16%,var(--card-background-color)); border-color:color-mix(in srgb,var(--warning-color,#f9a825) 35%,var(--divider-color)); }
          .remote-action.active .action-circle ha-icon { color:var(--warning-color,#f9a825); }
          .remote-action.warn .action-circle ha-icon { color:var(--error-color,#d32f2f); }
          .remote-action.experimental .action-circle { border-style:dashed; }
          .remote-action.busy, .remote-action.disabled { opacity:.48; pointer-events:none; }
          @media (max-width:600px) {
            .wrap { padding:14px; }
            .stage { min-height:245px; }
            .vehicle-status { max-width:118px; padding:6px 7px; }
            .vehicle-status span { display:none; }
            .vehicle-status ha-icon { --mdc-icon-size:21px; }
            .info-grid { grid-template-columns:repeat(2,minmax(0,1fr)); }
            .header h2 { font-size:18px; }
          }
        </style>
        <ha-card>
          <div class="wrap">
            <div class="header">
              <h2>${this._escape(this._headerTitle())}</h2>
              <div class="connection ${onlineKnown ? (online ? "online" : "") : "unknown"}"><i></i>${onlineKnown ? (online ? "Online" : "Offline") : "Нет данных"}</div>
            </div>
            <div class="stage">
              ${this._renderStatuses()}
              ${this._carSvg()}
            </div>
            ${this._renderInfo()}
            ${this._renderControls()}
          </div>
        </ha-card>`;

      this.shadowRoot.querySelectorAll("[data-action]").forEach((button) => {
        button.addEventListener("click", () => this._handleAction(button.dataset.action));
      });
    }

    _confirm(message) {
      if (this._config.confirm_controls === false) return true;
      return window.confirm(message);
    }

    async _runBusy(key, fn, onSuccess = null) {
      if (this._busy.has(key)) return;
      this._busy.add(key);
      this._render();
      try {
        await fn();
        if (onSuccess) onSuccess();
      } catch (err) {
        console.error(`[GWM Jolion Remote Card] ${key} failed`, err);
        alert(`GWM Jolion: ${err?.message || String(err)}`);
      } finally {
        this._busy.delete(key);
        this._render();
      }
    }

    async _handleAction(action) {
      if (!this._hass) return;
      const unlocked = this._isOn("unlocked");
      const engine = this._isOn("engine");
      const climate = this._isOn("climateOn") || this._state("climate")?.state === "heat_cool";
      const trunk = this._isOn("trunk");
      const windows = this._isOn("windows");

      if (action === "lock") {
        const entityId = this._entities.lock;
        if (!entityId) return alert("GWM Jolion: сущность центрального замка не найдена");
        if (!this._confirm(unlocked ? "Закрыть автомобиль?" : "Открыть автомобиль?")) return;
        return this._runBusy(action, () => this._hass.callService("lock", unlocked ? "lock" : "unlock", { entity_id: entityId }));
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
        return this._runBusy(action, () => this._hass.callService(INTEGRATION, engine ? "stop_engine" : "start_engine", engine ? {} : { operation_time: 15 }));
      }

      if (action === "climate") {
        const entityId = this._entities.climate;
        if (!entityId) return alert("GWM Jolion: сущность климата не найдена");
        if (!this._confirm(climate ? "Выключить климат?" : "Включить климат? На автомобиле с ДВС может запуститься двигатель.")) return;
        return this._runBusy(action, () => this._hass.callService("climate", climate ? "turn_off" : "turn_on", { entity_id: entityId }));
      }

      if (action === "trunk") {
        if (!this._confirm(trunk ? "Закрыть багажник?" : "Открыть багажник?")) return;
        return this._runBusy(action, () => this._hass.callService(INTEGRATION, trunk ? "close_trunk" : "open_trunk", {}));
      }

      if (action === "windows") {
        const openWindows = this._openWindows();
        const shouldClose = windows || openWindows.length > 0;
        if (!this._confirm(shouldClose ? "Закрыть все окна?" : "Открыть все окна? Команда открытия экспериментальная.")) return;
        return this._runBusy(action, () => this._hass.callService(INTEGRATION, shouldClose ? "close_windows" : "open_windows", {}));
      }

      if (action === "refresh") {
        const entityId = this._entities.refresh;
        if (!entityId) return alert("GWM Jolion: кнопка обновления не найдена");
        return this._runBusy(action, () => this._hass.callService("button", "press", { entity_id: entityId }));
      }

      if (action === "steering") return this._toggleComfort(action, "steeringHeat", "steering_wheel_heat_on", "steering_wheel_heat_off", "обогрев руля");
      if (action === "rear_defrost") return this._toggleComfort(action, "rearDefrost", "rear_defrost_on", "rear_defrost_off", "обогрев заднего стекла");
      if (action === "front_defrost") return this._toggleComfort(action, "frontDefrost", "front_defrost_on", "front_defrost_off", "передний defrost");
      if (action === "sunroof") return this._toggleRoof(action, "sunroofOpen", "open_sunroof", "close_sunroof", "панораму");
      if (action === "sunshade") return this._toggleRoof(action, "sunshadeOpen", "open_sunshade", "close_sunshade", "шторку");
    }

    async _toggleComfort(action, key, onService, offService, label) {
      const current = !this._isUnavailable(key) ? this._isOn(key) : Boolean(this._assumed[key]);
      const next = !current;
      if (!this._confirm(`${next ? "Включить" : "Выключить"} ${label}?`)) return;
      return this._runBusy(
        action,
        () => this._hass.callService(INTEGRATION, next ? onService : offService, {}),
        () => { this._assumed[key] = next; }
      );
    }

    async _toggleRoof(action, assumedKey, openService, closeService, label) {
      let current = this._assumed[assumedKey];
      if (current === undefined) {
        const open = window.confirm(`${label[0].toUpperCase()}${label.slice(1)}: ОК — открыть, Отмена — закрыть.`);
        current = !open;
      }
      const nextOpen = !current;
      if (this._config.confirm_controls !== false && !this._confirm(`${nextOpen ? "Открыть" : "Закрыть"} ${label}?`)) return;
      return this._runBusy(
        action,
        () => this._hass.callService(INTEGRATION, nextOpen ? openService : closeService, {}),
        () => { this._assumed[assumedKey] = nextOpen; }
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
      name: "GWM Jolion — пульт",
      description: "Настраиваемая карточка-пульт GWM Jolion с отдельным изображением автомобиля",
      preview: true,
      documentationURL: "https://github.com/IndeecDen/ha-gwm-jolion",
    });
  }

  console.info(
    `%c GWM JOLION REMOTE CARD %c ${CARD_VERSION} `,
    "background:#263238;color:white;font-weight:bold;padding:2px 6px;border-radius:3px",
    "background:#59656d;color:white;padding:2px 6px;border-radius:3px"
  );
})();
