/* GWM Jolion Card v0.1.0-alpha.8 */
(() => {
  const CARD_VERSION = "0.1.0-alpha.8";
  const INTEGRATION = "gwm_jolion";

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
    tireFlT: "_tire_fl_temp",
    tireFrT: "_tire_fr_temp",
    tireRlT: "_tire_rl_temp",
    tireRrT: "_tire_rr_temp",
    signal: "_tbox_signal_raw",
    lastCommand: "_last_command",
    steeringHeat: "_steering_wheel_heat_on",
    rearDefrost: "_rear_defrost_on",
    frontDefrost: "_front_defrost_on",
    windscreenHeat: "_front_windscreen_heat_on",
    seatDriver: "_driver_seat_heat_level_raw",
    seatPassenger: "_passenger_seat_heat_level_raw",
  };

  class GwmJolionCard extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: "open" });
      this._config = {};
      this._hass = null;
      this._entityRegistry = [];
      this._device = null;
      this._entities = {};
      this._resolving = false;
      this._resolvedKey = null;
      this._busy = new Set();
      this._engineRuntime = 15;
      this._assumed = {};
    }

    static getStubConfig() {
      return {};
    }

    static getGridOptions() {
      return { columns: 12, rows: 10, min_columns: 6, min_rows: 6 };
    }

    setConfig(config) {
      this._config = {
        confirm_controls: true,
        engine_runtime: 15,
        ...config,
      };
      const configuredRuntime = Number(this._config.engine_runtime);
      if (Number.isFinite(configuredRuntime)) {
        this._engineRuntime = Math.min(30, Math.max(5, configuredRuntime));
      }
      this._resolvedKey = null;
      if (this._hass) this._resolveEntities();
      this._render();
    }

    set hass(hass) {
      this._hass = hass;
      const key = `${this._config.device_id || ""}|${this._config.entity || ""}`;
      if (this._resolvedKey !== key && !this._resolving) {
        this._resolveEntities();
      }
      this._render();
    }

    getCardSize() {
      return 10;
    }

    async _resolveEntities() {
      if (!this._hass || this._resolving) return;
      this._resolving = true;
      try {
        const registry = await this._hass.callWS({
          type: "config/entity_registry/list",
        });
        this._entityRegistry = Array.isArray(registry) ? registry : [];

        let deviceId = this._config.device_id || null;
        if (!deviceId && this._config.entity) {
          const selected = this._entityRegistry.find(
            (entry) => entry.entity_id === this._config.entity
          );
          deviceId = selected?.device_id || null;
        }

        const gwmEntries = this._entityRegistry.filter(
          (entry) =>
            entry.platform === INTEGRATION ||
            (entry.config_entry_id && this._isGwmUniqueId(entry.unique_id))
        );

        if (!deviceId) {
          deviceId = gwmEntries.find((entry) => entry.device_id)?.device_id || null;
        }

        const vehicleEntries = deviceId
          ? gwmEntries.filter((entry) => entry.device_id === deviceId)
          : gwmEntries;

        const devices = await this._hass.callWS({
          type: "config/device_registry/list",
        });
        this._device = Array.isArray(devices)
          ? devices.find((device) => device.id === deviceId) || null
          : null;

        this._entities = {};
        for (const [key, suffix] of Object.entries(SUFFIX)) {
          const found = vehicleEntries.find((entry) =>
            String(entry.unique_id || "").endsWith(suffix)
          );
          if (found) this._entities[key] = found.entity_id;
        }

        this._entities.climate ||=
          vehicleEntries.find((entry) =>
            entry.entity_id.startsWith("climate.")
          )?.entity_id;
        this._entities.lock ||=
          vehicleEntries.find((entry) =>
            entry.entity_id.startsWith("lock.")
          )?.entity_id;
        this._entities.refresh ||=
          vehicleEntries.find(
            (entry) =>
              entry.entity_id.startsWith("button.") &&
              /refresh|obnov/i.test(entry.entity_id)
          )?.entity_id;

        this._resolvedKey = `${this._config.device_id || ""}|${this._config.entity || ""}`;
      } catch (err) {
        console.error("[GWM Jolion Card] entity discovery failed", err);
      } finally {
        this._resolving = false;
        this._render();
      }
    }

    _isGwmUniqueId(uniqueId) {
      if (!uniqueId) return false;
      return Object.values(SUFFIX).some((suffix) =>
        String(uniqueId).endsWith(suffix)
      );
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

    _featureOn(key) {
      if (!this._isUnavailable(key)) return this._isOn(key);
      return Boolean(this._assumed[key]);
    }

    _value(key, fallback = "—") {
      const stateObj = this._state(key);
      if (!stateObj || ["unknown", "unavailable", ""].includes(stateObj.state)) {
        return fallback;
      }
      const unit = stateObj.attributes?.unit_of_measurement;
      return `${stateObj.state}${unit ? ` ${unit}` : ""}`;
    }

    _rawValue(key) {
      const stateObj = this._state(key);
      if (!stateObj || ["unknown", "unavailable", ""].includes(stateObj.state)) {
        return null;
      }
      return String(stateObj.state);
    }

    _seatValue(key) {
      const raw = this._rawValue(key);
      if (raw === null) return "Нет данных · только статус";
      const value = Number(raw);
      if (Number.isFinite(value)) {
        return value === 0
          ? "Выключен · только статус"
          : `Уровень ${value} · только статус`;
      }
      return `${raw} · только статус`;
    }

    _drivetrain() {
      if (this._config.drivetrain) {
        return String(this._config.drivetrain).toUpperCase();
      }

      const raw = (this._rawValue("modelCode") || "").toUpperCase();
      if (!raw) return null;
      if (raw.includes("CC7150BA24C")) return "4WD";
      if (raw.includes("CC7150BA00B") || raw.includes("CC7150BA01B")) {
        return "2WD";
      }
      return null;
    }

    _headerTitle() {
      if (this._config.title) return String(this._config.title);

      const model = String(this._device?.model || "Haval Jolion").trim();
      const apiName = String(this._device?.name || "").trim();
      const drivetrain = this._drivetrain();
      const parts = [model];

      if (
        apiName &&
        apiName.toLocaleLowerCase() !== model.toLocaleLowerCase() &&
        apiName.toLocaleLowerCase() !== "gwm jolion"
      ) {
        parts.push(apiName);
      }
      if (drivetrain) parts.push(drivetrain);
      return parts.join(" ");
    }

    _openWindows() {
      const definitions = [
        ["windowFl", "переднее левое"],
        ["windowFr", "переднее правое"],
        ["windowRl", "заднее левое"],
        ["windowRr", "заднее правое"],
      ];
      const known = definitions.filter(([key]) => !this._isUnavailable(key));
      const open = known
        .filter(([key]) => this._isOn(key))
        .map(([, label]) => label);

      if (!known.length && this._isOn("windows")) {
        return ["одно или несколько окон"];
      }
      return open;
    }

    _windowSubtitle() {
      if (this._isUnavailable("windows")) return "Нет данных";
      const open = this._openWindows();
      if (open.length) {
        return `Открыты: ${open.join(", ")} · закрыть все`;
      }
      return "Все закрыты · открыть все";
    }

    _relativeUpdate() {
      const raw = this._rawValue("lastUpdate");
      if (!raw) return "Время обновления неизвестно";

      const then = new Date(raw).getTime();
      if (!Number.isFinite(then)) return "Время обновления неизвестно";

      const seconds = Math.max(0, Math.round((Date.now() - then) / 1000));
      if (seconds < 15) return "Обновлено только что";
      if (seconds < 60) return `Обновлено ${seconds} сек назад`;
      const minutes = Math.floor(seconds / 60);
      if (minutes < 60) return `Обновлено ${minutes} мин назад`;
      const hours = Math.floor(minutes / 60);
      if (hours < 24) return `Обновлено ${hours} ч назад`;
      const days = Math.floor(hours / 24);
      return `Обновлено ${days} дн назад`;
    }

    _labelBool(key, onLabel, offLabel, unknownLabel = "—") {
      if (this._isUnavailable(key)) return unknownLabel;
      return this._isOn(key) ? onLabel : offLabel;
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

    _statusChip(icon, label, tone = "safe") {
      return `<div class="chip ${tone}">${this._icon(icon)}<span>${this._escape(label)}</span></div>`;
    }

    _control(id, icon, title, subtitle, tone = "", disabled = false) {
      return `
        <button
          class="control ${tone} ${this._busy.has(id) ? "busy" : ""} ${disabled ? "disabled" : ""}"
          ${disabled ? "disabled" : `data-action="${id}"`}
          type="button"
        >
          ${this._icon(icon)}
          <span class="control-copy">
            <strong>${this._escape(title)}</strong>
            <small>${this._escape(subtitle)}</small>
          </span>
        </button>`;
    }

    _comfortControl(id, key, icon, title, { experimental = false } = {}) {
      const on = this._featureOn(key);
      const unknown = this._isUnavailable(key);
      const subtitle = unknown
        ? `${on ? "Выключить" : "Включить"}${experimental ? " · эксперимент" : ""}`
        : `${on ? "Включен · выключить" : "Выключен · включить"}${experimental ? " · эксперимент" : ""}`;
      return this._control(id, icon, title, subtitle, on ? "active" : "");
    }

    _readOnlyComfort(key, icon, title, value) {
      return this._control(
        `readonly-${key}`,
        icon,
        title,
        value,
        "readonly",
        true
      );
    }

    _roofControl(id, assumedKey, icon, title) {
      const assumed = this._assumed[assumedKey];
      const subtitle =
        assumed === true
          ? "Открыта · закрыть · эксперимент"
          : assumed === false
            ? "Закрыта · открыть · эксперимент"
            : "Открыть / закрыть · эксперимент";
      return this._control(id, icon, title, subtitle, "experimental");
    }

    _levelBars(rawValue, max, kind = "flat") {
      const number = Number(rawValue);
      if (!Number.isFinite(number)) {
        return `<span class="level unknown" title="Нет данных">—</span>`;
      }
      const active = Math.max(0, Math.min(max, Math.round(number)));
      const bars = [];
      for (let i = 1; i <= max; i += 1) {
        const height =
          kind === "signal"
            ? Math.round(4 + ((i - 1) / Math.max(1, max - 1)) * 10)
            : 10;
        bars.push(
          `<i class="${i <= active ? "on" : ""}" style="height:${height}px"></i>`
        );
      }
      return `<span class="level ${kind}" aria-label="${active} из ${max}">${bars.join("")}</span>`;
    }

    _tire(label, pKey, tKey) {
      return `
        <div class="tire">
          <strong>${label}</strong>
          <span>${this._escape(this._value(pKey))}</span>
          <small>${this._escape(this._value(tKey))}</small>
        </div>`;
    }

    _render() {
      if (!this.shadowRoot) return;
      if (!this._hass) {
        this.shadowRoot.innerHTML =
          `<ha-card><div style="padding:16px">GWM Jolion Card</div></ha-card>`;
        return;
      }

      const climate = this._state("climate");
      const targetTemp = Number(
        climate?.attributes?.temperature ??
          climate?.attributes?.target_temp ??
          22
      );
      const runtime = Number(
        this._state("climateRuntime")?.state ??
          climate?.attributes?.operation_time_minutes ??
          15
      );
      const engineRuntime = Number.isFinite(this._engineRuntime)
        ? this._engineRuntime
        : 15;

      const engineOn = this._isOn("engine");
      const unlocked = this._isOn("unlocked");
      const climateOn =
        this._isOn("climateOn") || climate?.state === "heat_cool";
      const trunkOpen = this._isOn("trunk");
      const windowsOpen = this._isOn("windows");
      const doorsOpen = this._isOn("doors");
      const online = this._isOn("tbox");

      const alerts = [
        doorsOpen
          ? this._statusChip("mdi:car-door-open", "Открыта дверь", "danger")
          : "",
        windowsOpen
          ? this._statusChip(
              "mdi:car-door",
              this._openWindows().length
                ? `Окна: ${this._openWindows().join(", ")}`
                : "Открыто окно",
              "danger"
            )
          : "",
        trunkOpen
          ? this._statusChip("mdi:car-back", "Открыт багажник", "danger")
          : "",
      ].filter(Boolean);

      const windscreenStatus = this._labelBool(
        "windscreenHeat",
        "Включен · только статус",
        "Выключен · только статус",
        "Нет данных · только статус"
      );

      this.shadowRoot.innerHTML = `
        <style>
          :host { display:block; }
          * { box-sizing:border-box; }
          ha-card {
            overflow:hidden;
            border-radius:var(--ha-card-border-radius,18px);
            background:var(--ha-card-background,var(--card-background-color));
          }
          .wrap { padding:18px; color:var(--primary-text-color); }
          .header {
            display:flex;
            justify-content:space-between;
            align-items:center;
            gap:12px;
          }
          .title {
            min-width:0;
            flex:1;
          }
          .title h2 {
            margin:0;
            font-size:21px;
            font-weight:700;
            line-height:1.2;
            white-space:nowrap;
            overflow:hidden;
            text-overflow:ellipsis;
          }
          .online {
            display:flex;
            align-items:center;
            gap:6px;
            font-size:12px;
            color:var(--secondary-text-color);
            white-space:nowrap;
          }
          .dot {
            width:9px;
            height:9px;
            border-radius:50%;
            background:var(--disabled-text-color);
          }
          .dot.on { background:var(--success-color,#43a047); }
          .stats {
            display:grid;
            grid-template-columns:repeat(4,minmax(0,1fr));
            gap:8px;
            margin-top:15px;
          }
          .stat {
            min-width:0;
            border-radius:13px;
            padding:10px;
            background:color-mix(
              in srgb,
              var(--primary-color) 6%,
              transparent
            );
          }
          .stat span {
            display:block;
            color:var(--secondary-text-color);
            font-size:10px;
            white-space:nowrap;
          }
          .stat b {
            display:block;
            margin-top:4px;
            font-size:13px;
            overflow:hidden;
            text-overflow:ellipsis;
            white-space:nowrap;
          }
          .chips {
            display:flex;
            gap:7px;
            flex-wrap:wrap;
            margin-top:10px;
          }
          .chip {
            display:flex;
            align-items:center;
            gap:5px;
            border-radius:999px;
            padding:7px 10px;
            font-size:12px;
            font-weight:600;
          }
          .chip ha-icon { --mdc-icon-size:17px; }
          .chip.danger {
            color:var(--error-color,#d32f2f);
            background:color-mix(
              in srgb,
              var(--error-color,#d32f2f) 11%,
              transparent
            );
          }
          .section { margin-top:18px; }
          .section-title {
            margin:0 0 9px;
            font-size:11px;
            letter-spacing:.09em;
            font-weight:700;
            color:var(--secondary-text-color);
            text-transform:uppercase;
          }
          .controls,
          .comfort {
            display:grid;
            grid-template-columns:repeat(3,minmax(0,1fr));
            gap:8px;
          }
          .control {
            appearance:none;
            border:0;
            text-align:left;
            min-width:0;
            min-height:66px;
            border-radius:14px;
            padding:11px;
            cursor:pointer;
            background:color-mix(
              in srgb,
              var(--primary-color) 7%,
              var(--card-background-color)
            );
            color:var(--primary-text-color);
            display:flex;
            gap:9px;
            align-items:center;
            transition:transform .12s ease,background .12s ease;
          }
          .control:hover {
            background:color-mix(
              in srgb,
              var(--primary-color) 12%,
              var(--card-background-color)
            );
          }
          .control:active { transform:scale(.98); }
          .control ha-icon {
            --mdc-icon-size:25px;
            color:var(--primary-color);
            flex:none;
          }
          .control.active ha-icon { color:var(--warning-color,#f9a825); }
          .control.danger ha-icon { color:var(--error-color,#d32f2f); }
          .control.experimental ha-icon { color:var(--warning-color,#f9a825); }
          .control.busy {
            opacity:.55;
            pointer-events:none;
          }
          .control.disabled {
            cursor:default;
            opacity:.58;
          }
          .control-copy {
            min-width:0;
            display:flex;
            flex-direction:column;
            gap:3px;
          }
          .control-copy strong {
            font-size:12px;
            white-space:nowrap;
            overflow:hidden;
            text-overflow:ellipsis;
          }
          .control-copy small {
            font-size:10px;
            color:var(--secondary-text-color);
            line-height:1.25;
            white-space:normal;
          }
          .timer-panel,
          .climate-panel {
            border-radius:16px;
            background:color-mix(in srgb,var(--primary-color) 6%,transparent);
            padding:14px;
          }
          .timer-panel { margin-top:9px; }
          .timer-head {
            display:flex;
            align-items:center;
            justify-content:space-between;
            gap:10px;
            margin-bottom:4px;
          }
          .timer-head span {
            display:flex;
            align-items:center;
            gap:7px;
            font-size:12px;
            color:var(--secondary-text-color);
          }
          .timer-head ha-icon { --mdc-icon-size:18px; }
          .runtime {
            display:flex;
            align-items:center;
            gap:10px;
            margin-top:10px;
          }
          .runtime input {
            flex:1;
            accent-color:var(--primary-color);
          }
          .runtime b {
            min-width:52px;
            text-align:right;
            font-size:12px;
          }
          .climate-top {
            display:grid;
            grid-template-columns:1fr;
            margin-bottom:10px;
          }
          .climate-main {
            display:grid;
            grid-template-columns:auto 1fr auto;
            gap:10px;
            align-items:center;
          }
          .temp-btn {
            width:38px;
            height:38px;
            border-radius:12px;
            border:0;
            cursor:pointer;
            background:var(--card-background-color);
            color:var(--primary-text-color);
            font-size:22px;
          }
          .temp { text-align:center; }
          .temp strong { font-size:27px; }
          .temp small {
            display:block;
            color:var(--secondary-text-color);
            margin-top:2px;
          }
          .comfort { margin-top:10px; }
          .tires {
            display:grid;
            grid-template-columns:repeat(4,1fr);
            gap:8px;
          }
          .tire {
            text-align:center;
            border-radius:13px;
            padding:10px 5px;
            background:color-mix(
              in srgb,
              var(--secondary-text-color) 5%,
              transparent
            );
          }
          .tire strong {
            display:block;
            color:var(--secondary-text-color);
            font-size:10px;
          }
          .tire span {
            display:block;
            font-size:13px;
            font-weight:700;
            margin-top:5px;
          }
          .tire small {
            display:block;
            color:var(--secondary-text-color);
            margin-top:2px;
          }
          .system {
            display:flex;
            flex-wrap:wrap;
            align-items:center;
            gap:14px;
            color:var(--secondary-text-color);
            font-size:12px;
          }
          .system-item {
            display:flex;
            align-items:center;
            gap:6px;
            min-height:20px;
          }
          .system-item ha-icon { --mdc-icon-size:17px; }
          .level {
            display:inline-flex;
            align-items:flex-end;
            gap:2px;
            height:15px;
          }
          .level i {
            display:block;
            width:4px;
            border-radius:1px;
            background:color-mix(
              in srgb,
              var(--secondary-text-color) 22%,
              transparent
            );
          }
          .level.flat i { width:5px; }
          .level i.on { background:var(--primary-color); }
          .level.unknown { align-items:center; }
          @media (max-width:600px) {
            .wrap { padding:14px; }
            .controls,
            .comfort {
              grid-template-columns:repeat(2,minmax(0,1fr));
            }
            .stats { grid-template-columns:repeat(2,minmax(0,1fr)); }
            .tires { grid-template-columns:repeat(2,1fr); }
            .title h2 { font-size:18px; }
          }
        </style>

        <ha-card>
          <div class="wrap">
            <div class="header">
              <div class="title">
                <h2>${this._escape(this._headerTitle())}</h2>
              </div>
              <div class="online">
                <span class="dot ${online ? "on" : ""}"></span>
                ${online ? "Online" : "Offline"}
              </div>
            </div>

            <div class="stats">
              <div class="stat">
                <span>Топливо л</span>
                <b>${this._escape(this._value("fuel"))}</b>
              </div>
              <div class="stat">
                <span>Топливо %</span>
                <b>${this._escape(this._value("fuelPercent"))}</b>
              </div>
              <div class="stat">
                <span>Запас</span>
                <b>${this._escape(this._value("range"))}</b>
              </div>
              <div class="stat">
                <span>Пробег</span>
                <b>${this._escape(this._value("mileage"))}</b>
              </div>
            </div>

            ${
              alerts.length
                ? `<div class="chips">${alerts.join("")}</div>`
                : ""
            }

            <div class="section">
              <div class="section-title">Управление</div>
              <div class="controls">
                ${this._control(
                  "engine",
                  engineOn ? "mdi:engine-off" : "mdi:engine",
                  "Двигатель",
                  engineOn ? "Остановить" : `Запустить · ${engineRuntime} мин`,
                  engineOn ? "active" : ""
                )}
                ${this._control(
                  "lock",
                  unlocked ? "mdi:lock" : "mdi:lock-open-variant",
                  "Замок",
                  unlocked ? "Закрыть" : "Открыть",
                  unlocked ? "active" : ""
                )}
                ${this._control(
                  "trunk",
                  "mdi:car-back",
                  "Багажник",
                  trunkOpen ? "Закрыть" : "Открыть",
                  trunkOpen ? "danger" : ""
                )}
                ${this._control(
                  "windows",
                  "mdi:car-door",
                  "Окна",
                  this._windowSubtitle(),
                  windowsOpen ? "danger" : ""
                )}
                ${this._roofControl(
                  "sunroof",
                  "sunroofOpen",
                  "mdi:car-select",
                  "Панорама"
                )}
                ${this._roofControl(
                  "sunshade",
                  "sunshadeOpen",
                  "mdi:blinds",
                  "Шторка"
                )}
                ${this._control(
                  "refresh",
                  "mdi:refresh",
                  "Обновить",
                  this._relativeUpdate()
                )}
              </div>

              <div class="timer-panel">
                <div class="timer-head">
                  <span>${this._icon("mdi:timer-outline")}Таймер автозапуска двигателя</span>
                  <b id="engine-runtime-label">${engineRuntime} мин</b>
                </div>
                <div class="runtime">
                  <input
                    id="engine-runtime"
                    type="range"
                    min="5"
                    max="30"
                    step="1"
                    value="${engineRuntime}"
                    ${engineOn ? "disabled" : ""}
                  >
                  <b>${engineRuntime} мин</b>
                </div>
              </div>
            </div>

            <div class="section">
              <div class="section-title">Климат</div>
              <div class="climate-panel">
                <div class="climate-top">
                  ${this._control(
                    "climate",
                    "mdi:air-conditioner",
                    "Кондиционер",
                    climateOn ? "Выключить" : "Включить",
                    climateOn ? "active" : ""
                  )}
                </div>

                <div class="climate-main">
                  <button class="temp-btn" data-temp-step="-1" type="button">−</button>
                  <div class="temp">
                    <strong>${Number.isFinite(targetTemp) ? targetTemp : 22} °C</strong>
                    <small>${climateOn ? "Работает" : "Выключен"}</small>
                  </div>
                  <button class="temp-btn" data-temp-step="1" type="button">+</button>
                </div>

                <div class="runtime">
                  ${this._icon("mdi:timer-outline")}
                  <input
                    id="runtime"
                    type="range"
                    min="5"
                    max="30"
                    step="1"
                    value="${Number.isFinite(runtime) ? runtime : 15}"
                  >
                  <b>${Number.isFinite(runtime) ? runtime : 15} мин</b>
                </div>

                <div class="comfort">
                  ${this._comfortControl(
                    "steering-heat",
                    "steeringHeat",
                    "mdi:steering",
                    "Обогрев руля"
                  )}
                  ${this._readOnlyComfort(
                    "seatDriver",
                    "mdi:car-seat-heater",
                    "Сиденье водителя",
                    this._seatValue("seatDriver")
                  )}
                  ${this._readOnlyComfort(
                    "seatPassenger",
                    "mdi:car-seat-heater",
                    "Сиденье пассажира",
                    this._seatValue("seatPassenger")
                  )}
                  ${this._comfortControl(
                    "rear-defrost",
                    "rearDefrost",
                    "mdi:car-defrost-rear",
                    "Обогрев заднего стекла"
                  )}
                  ${this._comfortControl(
                    "front-defrost",
                    "frontDefrost",
                    "mdi:car-defrost-front",
                    "Обдув лобового",
                    { experimental: true }
                  )}
                  ${this._readOnlyComfort(
                    "windscreenHeat",
                    "mdi:car-defrost-front",
                    "Обогрев лобового",
                    windscreenStatus
                  )}
                </div>
              </div>
            </div>

            <div class="section">
              <div class="section-title">Шины</div>
              <div class="tires">
                ${this._tire("ПЛ", "tireFlP", "tireFlT")}
                ${this._tire("ПП", "tireFrP", "tireFrT")}
                ${this._tire("ЗЛ", "tireRlP", "tireRlT")}
                ${this._tire("ЗП", "tireRrP", "tireRrT")}
              </div>
            </div>

            <div class="section">
              <div class="section-title">Система</div>
              <div class="system">
                <span class="system-item">
                  ${this._icon(online ? "mdi:cloud-check" : "mdi:cloud-off-outline")}
                  T-Box ${online ? "online" : "offline"}
                </span>
                <span class="system-item" title="Уровень GSM T-Box">
                  GSM ${this._levelBars(this._rawValue("signal"), 4, "signal")}
                </span>
                <span class="system-item">
                  ${this._icon("mdi:crosshairs-gps")}
                  GPS ${this._labelBool("gps", "есть", "нет")}
                </span>
                <span class="system-item" title="oilQty: шкала топлива GWM, 0–8 делений">
                  ${this._icon("mdi:gas-station")}
                  Топливо GWM ${this._levelBars(this._rawValue("oilQty"), 8, "flat")}
                </span>
                ${
                  this._state("lastCommand")
                    ? `<span class="system-item">${this._icon("mdi:cloud-check-outline")}${this._escape(this._value("lastCommand"))}</span>`
                    : ""
                }
              </div>
            </div>
          </div>
        </ha-card>`;

      this._bindActions();
    }

    _bindActions() {
      this.shadowRoot.querySelectorAll("[data-action]").forEach((button) =>
        button.addEventListener("click", () =>
          this._handleAction(button.dataset.action)
        )
      );

      this.shadowRoot.querySelectorAll("[data-temp-step]").forEach((button) =>
        button.addEventListener("click", () =>
          this._changeTemperature(Number(button.dataset.tempStep))
        )
      );

      const runtime = this.shadowRoot.getElementById("runtime");
      if (runtime) {
        runtime.addEventListener("change", () =>
          this._setRuntime(Number(runtime.value))
        );
      }

      const engineRuntime = this.shadowRoot.getElementById("engine-runtime");
      if (engineRuntime) {
        engineRuntime.addEventListener("input", () => {
          const value = Number(engineRuntime.value);
          if (!Number.isFinite(value)) return;
          this._engineRuntime = value;
          const label = this.shadowRoot.getElementById("engine-runtime-label");
          if (label) label.textContent = `${value} мин`;
          const rightValue = engineRuntime.parentElement?.querySelector("b");
          if (rightValue) rightValue.textContent = `${value} мин`;
        });
      }
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
        console.error(`[GWM Jolion Card] ${key} failed`, err);
        alert(`GWM Jolion: ${err?.message || String(err)}`);
      } finally {
        this._busy.delete(key);
        this._render();
      }
    }

    async _handleAction(action) {
      if (!this._hass) return;

      const engineOn = this._isOn("engine");
      const unlocked = this._isOn("unlocked");
      const climateOn =
        this._isOn("climateOn") ||
        this._state("climate")?.state === "heat_cool";
      const trunkOpen = this._isOn("trunk");
      const windowsOpen = this._isOn("windows");

      if (action === "engine") {
        const runtime = Math.min(
          30,
          Math.max(5, Number(this._engineRuntime) || 15)
        );
        const message = engineOn
          ? "Остановить двигатель?"
          : `Запустить двигатель на ${runtime} мин? Машина должна быть закрыта.`;
        if (!this._confirm(message)) return;
        return this._runBusy(action, () =>
          this._hass.callService(
            INTEGRATION,
            engineOn ? "stop_engine" : "start_engine",
            engineOn ? {} : { operation_time: runtime }
          )
        );
      }

      if (action === "lock") {
        const entityId = this._entities.lock;
        if (!entityId) {
          return alert("GWM Jolion: сущность центрального замка не найдена");
        }
        if (
          !this._confirm(
            unlocked ? "Закрыть автомобиль?" : "Разблокировать автомобиль?"
          )
        ) {
          return;
        }
        return this._runBusy(action, () =>
          this._hass.callService("lock", unlocked ? "lock" : "unlock", {
            entity_id: entityId,
          })
        );
      }

      if (action === "climate") {
        const entityId = this._entities.climate;
        if (!entityId) {
          return alert("GWM Jolion: сущность климата не найдена");
        }
        if (
          !this._confirm(
            climateOn
              ? "Выключить кондиционер?"
              : "Запустить кондиционер? На автомобиле с ДВС может запуститься двигатель."
          )
        ) {
          return;
        }
        return this._runBusy(action, () =>
          this._hass.callService(
            "climate",
            climateOn ? "turn_off" : "turn_on",
            { entity_id: entityId }
          )
        );
      }

      if (action === "trunk") {
        if (
          !this._confirm(
            trunkOpen ? "Закрыть багажник?" : "Открыть багажник?"
          )
        ) {
          return;
        }
        return this._runBusy(action, () =>
          this._hass.callService(
            INTEGRATION,
            trunkOpen ? "close_trunk" : "open_trunk",
            {}
          )
        );
      }

      if (action === "windows") {
        const open = this._openWindows();
        const shouldClose = windowsOpen || open.length > 0;
        const message = shouldClose
          ? `Закрыть все окна${open.length ? `? Сейчас открыты: ${open.join(", ")}.` : "?"}`
          : "Открыть все окна? Команда открытия пока экспериментальная.";
        if (!this._confirm(message)) return;
        return this._runBusy(action, () =>
          this._hass.callService(
            INTEGRATION,
            shouldClose ? "close_windows" : "open_windows",
            {}
          )
        );
      }

      if (action === "refresh") {
        const entityId = this._entities.refresh;
        if (!entityId) {
          return alert("GWM Jolion: кнопка обновления не найдена");
        }
        return this._runBusy(action, () =>
          this._hass.callService("button", "press", { entity_id: entityId })
        );
      }

      if (action === "sunroof") {
        return this._toggleRoof(
          action,
          "sunroofOpen",
          "open_sunroof",
          "close_sunroof",
          "панораму"
        );
      }

      if (action === "sunshade") {
        return this._toggleRoof(
          action,
          "sunshadeOpen",
          "open_sunshade",
          "close_sunshade",
          "шторку"
        );
      }

      if (action === "steering-heat") {
        return this._toggleComfort(
          action,
          "steeringHeat",
          "steering_wheel_heat_on",
          "steering_wheel_heat_off",
          "обогрев руля"
        );
      }

      if (action === "rear-defrost") {
        return this._toggleComfort(
          action,
          "rearDefrost",
          "rear_defrost_on",
          "rear_defrost_off",
          "обогрев заднего стекла"
        );
      }

      if (action === "front-defrost") {
        return this._toggleComfort(
          action,
          "frontDefrost",
          "front_defrost_on",
          "front_defrost_off",
          "обдув лобового стекла"
        );
      }
    }

    async _toggleRoof(action, assumedKey, openService, closeService, label) {
      let current = this._assumed[assumedKey];
      if (current === undefined) {
        const open = window.confirm(
          `${label[0].toUpperCase()}${label.slice(1)}: ОК — открыть, Отмена — закрыть.`
        );
        current = !open;
      }
      const nextOpen = !current;
      const service = nextOpen ? openService : closeService;
      if (
        this._config.confirm_controls !== false &&
        !this._confirm(`${nextOpen ? "Открыть" : "Закрыть"} ${label}?`)
      ) {
        return;
      }
      return this._runBusy(
        action,
        () => this._hass.callService(INTEGRATION, service, {}),
        () => {
          this._assumed[assumedKey] = nextOpen;
        }
      );
    }

    async _toggleComfort(action, key, onService, offService, label) {
      const isOn = this._featureOn(key);
      const nextOn = !isOn;
      if (!this._confirm(`${nextOn ? "Включить" : "Выключить"} ${label}?`)) {
        return;
      }

      return this._runBusy(
        action,
        () =>
          this._hass.callService(
            INTEGRATION,
            nextOn ? onService : offService,
            {}
          ),
        () => {
          this._assumed[key] = nextOn;
        }
      );
    }

    async _changeTemperature(step) {
      const climate = this._state("climate");
      const entityId = this._entities.climate;
      if (!climate || !entityId) return;
      const current = Number(climate.attributes?.temperature ?? 22);
      const min = Number(climate.attributes?.min_temp ?? 16);
      const max = Number(climate.attributes?.max_temp ?? 32);
      const next = Math.min(max, Math.max(min, current + step));
      await this._runBusy("temperature", () =>
        this._hass.callService("climate", "set_temperature", {
          entity_id: entityId,
          temperature: next,
        })
      );
    }

    async _setRuntime(value) {
      const entityId = this._entities.climateRuntime;
      if (!entityId || !Number.isFinite(value)) return;
      await this._runBusy("runtime", () =>
        this._hass.callService("number", "set_value", {
          entity_id: entityId,
          value,
        })
      );
    }
  }

  if (!customElements.get("gwm-jolion-card")) {
    customElements.define("gwm-jolion-card", GwmJolionCard);
  }

  window.customCards = window.customCards || [];
  if (!window.customCards.some((card) => card.type === "gwm-jolion-card")) {
    window.customCards.push({
      type: "gwm-jolion-card",
      name: "GWM Jolion",
      description: "Карточка автомобиля Haval Jolion для интеграции GWM Jolion",
      preview: true,
      documentationURL: "https://github.com/IndeecDen/ha-gwm-jolion",
    });
  }

  console.info(
    `%c GWM JOLION CARD %c ${CARD_VERSION} `,
    "background:#1976d2;color:white;font-weight:bold;padding:2px 6px;border-radius:3px",
    "background:#263238;color:white;padding:2px 6px;border-radius:3px"
  );
})();
