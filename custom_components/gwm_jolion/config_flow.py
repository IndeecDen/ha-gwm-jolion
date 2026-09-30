"""Config flow for GWM Jolion."""

from __future__ import annotations

from typing import Any
from uuid import uuid4
import hashlib
import re

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import voluptuous as vol

from .api import GwmJolionApiClient
from .capabilities import MANUAL_CAPABILITY_OPTIONS, resolve_manual_capabilities
from .const import (
    CONF_COMMAND_COOLDOWN, CONF_COUNTRY, CONF_COUNTRY_CODE, CONF_DEVICE_ID,
    CONF_ENABLE_REMOTE_CONTROLS, CONF_PHONE, CONF_GPS_INTERVAL, CONF_POLL_INTERVAL, CONF_SECURITY_PIN,
    DEFAULT_COMMAND_COOLDOWN, DEFAULT_COUNTRY, DEFAULT_COUNTRY_CODE,
    DEFAULT_ENABLE_REMOTE_CONTROLS, DEFAULT_POLL_INTERVAL, DEFAULT_GPS_INTERVAL, MIN_GPS_INTERVAL, DOMAIN,
)
from .helpers import normalize_phone
from .protocol_capture import CONF_PROTOCOL_CAPTURE, DEFAULT_PROTOCOL_CAPTURE
from .locator import (ENABLED as LOCATOR_ENABLED, VEHICLE_ID as LOCATOR_ID,
    KEY_HASH as LOCATOR_HASH, UPLOAD_KEY as LOCATOR_KEY,
    DISK_OAUTH as TOKEN, DISK_FOLDER as FOLDER,
    DISK_CLEANUP as CLEANUP, DISK_CLEANUP_GRACE_HOURS as CLEANUP_GRACE_HOURS,
    DISK_RELAY_INTERVAL, DEFAULT_DISK_FOLDER, DEFAULT_RELAY_INTERVAL,
    MIN_RELAY_INTERVAL, MAX_RELAY_INTERVAL)

CLEAR_SECURITY_PIN = "clear_security_pin"
POLL_INTERVAL_SELECTOR = selector.NumberSelector(selector.NumberSelectorConfig(
    min=30, max=3600, step=1, mode=selector.NumberSelectorMode.SLIDER, unit_of_measurement="сек"))

GPS_INTERVAL_SELECTOR = selector.NumberSelector(selector.NumberSelectorConfig(
    min=MIN_GPS_INTERVAL, max=3600, step=1, mode=selector.NumberSelectorMode.SLIDER, unit_of_measurement="сек"))

STEP_USER_DATA_SCHEMA = vol.Schema({
    vol.Optional(CONF_GPS_INTERVAL, default=DEFAULT_GPS_INTERVAL): GPS_INTERVAL_SELECTOR,
    vol.Required(CONF_PHONE): str,
    vol.Required(CONF_PASSWORD): selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)),
    vol.Optional(CONF_POLL_INTERVAL, default=DEFAULT_POLL_INTERVAL): POLL_INTERVAL_SELECTOR,
    vol.Optional(CONF_ENABLE_REMOTE_CONTROLS, default=DEFAULT_ENABLE_REMOTE_CONTROLS): bool,
    vol.Optional(CONF_SECURITY_PIN): selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)),
})


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    phone = normalize_phone(data[CONF_PHONE])
    device_id = str(data.get(CONF_DEVICE_ID) or uuid4().hex)
    client = GwmJolionApiClient(
        async_get_clientsession(hass),
        phone=phone,
        password=data[CONF_PASSWORD],
        device_id=device_id,
        country=DEFAULT_COUNTRY,
        country_code=DEFAULT_COUNTRY_CODE,
    )
    await client.async_login()
    return {"title": f"Haval Jolion ••••{phone[-4:]}", "phone": phone, "device_id": device_id}


class GwmJolionConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 2

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except ConfigEntryAuthFailed:
                errors["base"] = "invalid_auth"
            except HomeAssistantError:
                errors["base"] = "cannot_connect"
            except Exception:
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(info["phone"])
                self._abort_if_unique_id_configured()
                options = {
                    CONF_POLL_INTERVAL: user_input.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
                    CONF_ENABLE_REMOTE_CONTROLS: user_input.get(CONF_ENABLE_REMOTE_CONTROLS, DEFAULT_ENABLE_REMOTE_CONTROLS),
                    CONF_GPS_INTERVAL: int(user_input.get(CONF_GPS_INTERVAL, DEFAULT_GPS_INTERVAL)),
                    CONF_COMMAND_COOLDOWN: DEFAULT_COMMAND_COOLDOWN,
                    CONF_PROTOCOL_CAPTURE: DEFAULT_PROTOCOL_CAPTURE,
                }
                if user_input.get(CONF_SECURITY_PIN):
                    options[CONF_SECURITY_PIN] = user_input[CONF_SECURITY_PIN]
                return self.async_create_entry(
                    title=info["title"],
                    data={
                        CONF_PHONE: info["phone"],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_COUNTRY: DEFAULT_COUNTRY,
                        CONF_COUNTRY_CODE: DEFAULT_COUNTRY_CODE,
                        CONF_DEVICE_ID: info["device_id"],
                    },
                    options=options,
                )
        return self.async_show_form(step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors)

    async def async_step_reauth(self, user_input: dict[str, Any] | None = None):
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                data = dict(entry.data)
                data[CONF_PASSWORD] = user_input[CONF_PASSWORD]
                await validate_input(self.hass, data)
                self.hass.config_entries.async_update_entry(entry, data=data)
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reauth_successful")
            except ConfigEntryAuthFailed:
                errors["base"] = "invalid_auth"
            except HomeAssistantError:
                errors["base"] = "cannot_connect"
            except Exception:
                errors["base"] = "unknown"
        return self.async_show_form(
            step_id="reauth",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD))}),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        return GwmJolionOptionsFlow()


class GwmJolionOptionsFlow(config_entries.OptionsFlowWithReload):
    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        errors = {}
        if user_input is not None:
            options = dict(self.config_entry.options)
            options[LOCATOR_ENABLED] = bool(user_input.get(LOCATOR_ENABLED, options.get(LOCATOR_ENABLED, False)))
            locator_id = str(user_input.get(LOCATOR_ID, options.get(LOCATOR_ID, "jolion"))).strip()
            locator_key = str(user_input.get(LOCATOR_KEY, "")).strip()
            if locator_key and not re.fullmatch(r"[A-Za-z0-9_-]{32,128}", locator_key):
                errors[LOCATOR_KEY] = "invalid_locator_key"
            if options[LOCATOR_ENABLED]:
                if not re.fullmatch(r"[a-z0-9_-]{1,40}", locator_id):
                    errors[LOCATOR_ID] = "invalid_locator_id"
                elif any(e.entry_id != self.config_entry.entry_id and e.options.get(LOCATOR_ENABLED) and e.options.get(LOCATOR_ID) == locator_id for e in self.hass.config_entries.async_entries(DOMAIN)):
                    errors[LOCATOR_ID] = "duplicate_locator_id"
                if locator_key and not re.fullmatch(r"[A-Za-z0-9_-]{32,128}", locator_key):
                    errors[LOCATOR_KEY] = "invalid_locator_key"
                elif not locator_key and not options.get(LOCATOR_HASH):
                    errors[LOCATOR_KEY] = "invalid_locator_key"
            transport=user_input.get("golion_locator_transport", options.get("golion_locator_transport","https"))
            public_url=str(user_input.get("golion_locator_yandex_public_url",options.get("golion_locator_yandex_public_url",""))).strip()
            # Imported here so that the form can be shown without pulling in the
            # cryptography dependency of the relay module.
            from .locator_yandex import valid_disk_token, valid_folder, valid_public_url
            disk_token=str(user_input.get(TOKEN, options.get(TOKEN,""))).strip()
            disk_folder=str(user_input.get(FOLDER, options.get(FOLDER,DEFAULT_DISK_FOLDER))).strip()
            disk_cleanup=bool(user_input.get(CLEANUP, options.get(CLEANUP,False)))
            try:
                grace_hours=int(user_input.get(CLEANUP_GRACE_HOURS, options.get(CLEANUP_GRACE_HOURS,24)))
            except (TypeError,ValueError):
                grace_hours=0
            try:
                interval=int(user_input.get(DISK_RELAY_INTERVAL, options.get(DISK_RELAY_INTERVAL,DEFAULT_RELAY_INTERVAL)))
            except (TypeError,ValueError):
                interval=0
            if not MIN_RELAY_INTERVAL<=interval<=MAX_RELAY_INTERVAL:errors[DISK_RELAY_INTERVAL]="invalid_relay_interval"
            if transport not in ("https","yandex_disk"):errors["golion_locator_transport"]="invalid_transport"
            if disk_token and not valid_disk_token(disk_token):errors[TOKEN]="invalid_disk_token"
            if not valid_folder(disk_folder):errors[FOLDER]="invalid_disk_folder"
            if not 1<=grace_hours<=168:errors[CLEANUP_GRACE_HOURS]="invalid_cleanup_grace"
            if options[LOCATOR_ENABLED] and transport=="yandex_disk":
                if not valid_public_url(public_url):errors["golion_locator_yandex_public_url"]="invalid_yandex_url"
                if not locator_key and not options.get(LOCATOR_KEY):errors[LOCATOR_KEY]="invalid_locator_key"
            # Cleanup moves files to the Disk trash, so it requires a token with
            # write access plus a folder the user has confirmed.
            if disk_cleanup and not (disk_token or options.get(TOKEN)):
                errors[TOKEN]="missing_disk_token"
            if transport!="yandex_disk" and disk_cleanup:
                errors[CLEANUP]="cleanup_needs_disk"
            options["golion_locator_transport"]=transport
            options["golion_locator_yandex_public_url"]=public_url
            options[FOLDER]=disk_folder
            options[CLEANUP]=disk_cleanup and transport=="yandex_disk"
            options[CLEANUP_GRACE_HOURS]=grace_hours
            options[DISK_RELAY_INTERVAL]=interval
            if disk_token:options[TOKEN]=disk_token
            options[LOCATOR_ID] = locator_id
            if locator_key and not errors:
                options[LOCATOR_HASH] = hashlib.sha256(locator_key.encode()).hexdigest()
                options[LOCATOR_KEY] = locator_key
            options["trip_retention_days"] = int(user_input.get("trip_retention_days", options.get("trip_retention_days", 90)))
            options[CONF_GPS_INTERVAL] = int(user_input.get(CONF_GPS_INTERVAL, options.get(CONF_GPS_INTERVAL, options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL))))
            options[CONF_POLL_INTERVAL] = user_input.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)
            options[CONF_ENABLE_REMOTE_CONTROLS] = user_input.get(CONF_ENABLE_REMOTE_CONTROLS, DEFAULT_ENABLE_REMOTE_CONTROLS)
            options[CONF_COMMAND_COOLDOWN] = user_input.get(CONF_COMMAND_COOLDOWN, DEFAULT_COMMAND_COOLDOWN)
            options[CONF_PROTOCOL_CAPTURE] = bool(user_input.get(CONF_PROTOCOL_CAPTURE, DEFAULT_PROTOCOL_CAPTURE))
            if user_input.get(CONF_SECURITY_PIN):
                options[CONF_SECURITY_PIN] = user_input[CONF_SECURITY_PIN]
            if user_input.get(CLEAR_SECURITY_PIN):
                options.pop(CONF_SECURITY_PIN, None)
            for option_key in MANUAL_CAPABILITY_OPTIONS.values():
                options[option_key] = bool(user_input.get(option_key, True))
            if not errors:
                return self.async_create_entry(title="", data=options)

        current = {**self.config_entry.options, **(user_input or {})}
        has_pin = bool(current.get(CONF_SECURITY_PIN))
        feature_defaults = resolve_manual_capabilities(dict(current))
        schema: dict[vol.Marker, Any] = {
            vol.Optional(LOCATOR_ENABLED, default=current.get(LOCATOR_ENABLED, False)): bool,
            vol.Optional("golion_locator_transport", default=current.get("golion_locator_transport","https")): vol.In({"https":"Напрямую HTTPS","yandex_disk":"Яндекс.Диск (публичная папка)"}),
            vol.Optional("golion_locator_yandex_public_url", default=current.get("golion_locator_yandex_public_url","")): str,
            vol.Optional(TOKEN, default=current.get(TOKEN, "")): selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)),
            vol.Optional(FOLDER, default=current.get(FOLDER, "/JolionLocator")): str,
            vol.Optional(CLEANUP, default=bool(current.get(CLEANUP, False))): bool,
            vol.Optional(CLEANUP_GRACE_HOURS, default=current.get(CLEANUP_GRACE_HOURS, 24)): vol.All(int, vol.Range(min=1, max=168)),
            vol.Optional(DISK_RELAY_INTERVAL, default=current.get(DISK_RELAY_INTERVAL, DEFAULT_RELAY_INTERVAL)): vol.All(int, vol.Range(min=MIN_RELAY_INTERVAL, max=MAX_RELAY_INTERVAL)),
            vol.Optional(LOCATOR_ID, default=current.get(LOCATOR_ID, "jolion")): str,
            vol.Optional(LOCATOR_KEY, default=current.get(LOCATOR_KEY, "")): selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)),
            vol.Optional("trip_retention_days", default=current.get("trip_retention_days", 90)): vol.All(int, vol.Range(min=30, max=365)),
            vol.Optional(CONF_GPS_INTERVAL, default=current.get(CONF_GPS_INTERVAL, current.get(CONF_POLL_INTERVAL, self.config_entry.data.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)))): GPS_INTERVAL_SELECTOR,
            vol.Optional(CONF_POLL_INTERVAL, default=current.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)): POLL_INTERVAL_SELECTOR,
            vol.Optional(CONF_ENABLE_REMOTE_CONTROLS, default=current.get(CONF_ENABLE_REMOTE_CONTROLS, DEFAULT_ENABLE_REMOTE_CONTROLS)): bool,
            vol.Optional(CONF_COMMAND_COOLDOWN, default=current.get(CONF_COMMAND_COOLDOWN, DEFAULT_COMMAND_COOLDOWN)): vol.All(int, vol.Range(min=10, max=120)),
            vol.Optional(CONF_PROTOCOL_CAPTURE, default=bool(current.get(CONF_PROTOCOL_CAPTURE, DEFAULT_PROTOCOL_CAPTURE))): bool,
            vol.Optional(CONF_SECURITY_PIN): selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)),
            vol.Optional(CLEAR_SECURITY_PIN, default=False): bool,
        }
        for capability, option_key in MANUAL_CAPABILITY_OPTIONS.items():
            schema[vol.Optional(option_key, default=feature_defaults[capability])] = bool
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema),
            errors=errors,
            description_placeholders={
                "pin_status": "сохранён" if has_pin else "не задан",
                "locator_url": f"/gwm-jolion-pairing?entry_id={self.config_entry.entry_id}",
            },
        )
