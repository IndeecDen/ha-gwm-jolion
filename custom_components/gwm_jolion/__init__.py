"""GWM Jolion integration."""

from __future__ import annotations

import logging
from pathlib import Path
from uuid import uuid4

import voluptuous as vol

from homeassistant.components import frontend
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import GwmJolionApiClient
from .capabilities import resolve_manual_capabilities
from .commands import COMMANDS, UNSUPPORTED_COMMANDS
from .const import (
    CONF_COMMAND_COOLDOWN, CONF_COUNTRY, CONF_COUNTRY_CODE, CONF_DEVICE_ID,
    CONF_ENABLE_REMOTE_CONTROLS, CONF_PHONE, CONF_POLL_INTERVAL, CONF_SECURITY_PIN,
    DEFAULT_COMMAND_COOLDOWN, DEFAULT_COUNTRY, DEFAULT_COUNTRY_CODE,
    DEFAULT_ENABLE_REMOTE_CONTROLS, DEFAULT_POLL_INTERVAL, DOMAIN, PLATFORMS,
)
from .coordinator import GwmJolionCoordinator
from .entity_surface import MIGRATION_REMOVE_ENTITY_SUFFIXES, OBSOLETE_OPTION_KEYS
from .protocol_capture import (
    CAPTURE_DIRECTORY,
    CONF_PROTOCOL_CAPTURE,
    DEFAULT_PROTOCOL_CAPTURE,
    new_capture_path,
)

_LOGGER = logging.getLogger(__name__)

FRONTEND_DIR = Path(__file__).parent / "frontend"
FRONTEND_ASSETS = (
    (
        FRONTEND_DIR / "gwm-jolion-card-editor.js",
        "/gwm-jolion/gwm-jolion-card-editor.js",
        "/gwm-jolion/gwm-jolion-card-editor.js?v=0.1.0-beta.5",
    ),
    (
        FRONTEND_DIR / "gwm-jolion-card.js",
        "/gwm-jolion/gwm-jolion-card.js",
        "/gwm-jolion/gwm-jolion-card.js?v=0.1.0-beta.5",
    ),
    (
        FRONTEND_DIR / "gwm-jolion-remote-card.js",
        "/gwm-jolion/gwm-jolion-remote-card.js",
        "/gwm-jolion/gwm-jolion-remote-card.js?v=0.1.0-beta.5",
    ),
    (
        FRONTEND_DIR / "gwm-jolion-alpha20.js",
        "/gwm-jolion/gwm-jolion-alpha20.js",
        "/gwm-jolion/gwm-jolion-alpha20.js?v=0.1.0-beta.5",
    ),
)
DATA_FRONTEND_REGISTERED = "_frontend_registered"
SERVICE_ADD_CAPTURE_MARKER = "add_capture_marker"
CONFIG_ENTRY_VERSION = 2


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Remove obsolete alpha entities and options once when upgrading to v2."""
    if entry.version > CONFIG_ENTRY_VERSION:
        _LOGGER.error(
            "Cannot migrate GWM Jolion config entry from future version %s",
            entry.version,
        )
        return False

    if entry.version < CONFIG_ENTRY_VERSION:
        registry = er.async_get(hass)
        removed: list[str] = []
        for domain, suffixes in MIGRATION_REMOVE_ENTITY_SUFFIXES.items():
            for suffix in suffixes:
                unique_id = f"{entry.entry_id}_{suffix}"
                entity_id = registry.async_get_entity_id(domain, DOMAIN, unique_id)
                if entity_id:
                    registry.async_remove(entity_id)
                    removed.append(entity_id)

        options = dict(entry.options)
        for key in OBSOLETE_OPTION_KEYS:
            options.pop(key, None)

        hass.config_entries.async_update_entry(
            entry,
            version=CONFIG_ENTRY_VERSION,
            options=options,
        )
        _LOGGER.info(
            "Migrated GWM Jolion entity surface to alpha.20: removed %d obsolete registry entries",
            len(removed),
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    await _async_register_frontend(hass)

    registry = er.async_get(hass)
    for key in UNSUPPORTED_COMMANDS:
        entity_id = registry.async_get_entity_id("button", DOMAIN, f"{entry.entry_id}_cmd_{key}")
        if entity_id:
            registry.async_remove(entity_id)

    data = dict(entry.data)
    options = dict(entry.options)
    device_id = data.get(CONF_DEVICE_ID) or uuid4().hex
    client = GwmJolionApiClient(
        async_get_clientsession(hass),
        phone=data[CONF_PHONE],
        password=data[CONF_PASSWORD],
        device_id=device_id,
        country=data.get(CONF_COUNTRY, DEFAULT_COUNTRY),
        country_code=data.get(CONF_COUNTRY_CODE, DEFAULT_COUNTRY_CODE),
    )
    capture_enabled = bool(options.get(CONF_PROTOCOL_CAPTURE, DEFAULT_PROTOCOL_CAPTURE))
    capture_path = None
    if capture_enabled:
        capture_path = str(new_capture_path(hass.config.path(CAPTURE_DIRECTORY)))
        _LOGGER.warning("GWM protocol capture enabled: %s", capture_path)

    coordinator = GwmJolionCoordinator(
        hass,
        client,
        int(options.get(CONF_POLL_INTERVAL, data.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL))),
        entry.entry_id,
        enable_remote_controls=bool(options.get(CONF_ENABLE_REMOTE_CONTROLS, DEFAULT_ENABLE_REMOTE_CONTROLS)),
        command_cooldown=int(options.get(CONF_COMMAND_COOLDOWN, DEFAULT_COMMAND_COOLDOWN)),
        security_pin=str(options.get(CONF_SECURITY_PIN)) if options.get(CONF_SECURITY_PIN) else None,
        feature_flags=resolve_manual_capabilities(options),
        protocol_capture_enabled=capture_enabled,
        protocol_capture_path=capture_path,
    )
    await coordinator.async_load_card_settings()
    await coordinator.async_load_profiles()
    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _register_services(hass)
    return True


async def _async_register_frontend(hass: HomeAssistant) -> None:
    """Serve and load bundled Lovelace cards once per HA process."""
    if hass.data[DOMAIN].get(DATA_FRONTEND_REGISTERED):
        return

    available_assets = [asset for asset in FRONTEND_ASSETS if asset[0].exists()]
    missing_assets = [asset[0] for asset in FRONTEND_ASSETS if not asset[0].exists()]
    for path in missing_assets:
        _LOGGER.warning("Bundled GWM Jolion card was not found at %s", path)

    if not available_assets:
        return

    await hass.http.async_register_static_paths(
        [StaticPathConfig(static_url, str(path), False) for path, static_url, _ in available_assets]
    )
    for _, _, frontend_url in available_assets:
        frontend.add_extra_js_url(hass, frontend_url)

    hass.data[DOMAIN][DATA_FRONTEND_REGISTERED] = True
    _LOGGER.debug(
        "Registered bundled GWM Jolion cards: %s",
        ", ".join(frontend_url for _, _, frontend_url in available_assets),
    )


def _coordinators(hass: HomeAssistant) -> list[GwmJolionCoordinator]:
    return [
        value
        for value in (hass.data.get(DOMAIN) or {}).values()
        if isinstance(value, GwmJolionCoordinator)
    ]


def _register_services(hass: HomeAssistant) -> None:
    """Keep advanced services for compatibility; public UI uses native entities/buttons."""

    def select_coordinator(call: ServiceCall) -> GwmJolionCoordinator:
        candidates = _coordinators(hass)
        entry_id = call.data.get("entry_id")
        if entry_id:
            candidates = [item for item in candidates if item.entry_id == entry_id]
        if len(candidates) != 1:
            raise HomeAssistantError("Укажите entry_id нужного автомобиля GWM")
        return candidates[0]

    async def handle_seat_heating(call: ServiceCall) -> None:
        await select_coordinator(call).async_set_seat_heating(
            call.data.get("driver"), call.data.get("passenger"), call.data["operation_time"]
        )

    if not hass.services.has_service(DOMAIN, "set_seat_heating"):
        hass.services.async_register(DOMAIN, "set_seat_heating", handle_seat_heating, schema=vol.Schema({
            vol.Optional("entry_id"): str,
            vol.Optional("driver"): vol.All(int, vol.Range(min=0, max=3)),
            vol.Optional("passenger"): vol.All(int, vol.Range(min=0, max=3)),
            vol.Optional("operation_time", default=5): vol.All(int, vol.Range(min=1, max=10)),
        }))

    async def handle_comfort_start(call: ServiceCall) -> None:
        await select_coordinator(call).async_start_with_comfort(
            temperature=call.data["temperature"], climate_time=call.data["climate_time"],
            engine_time=call.data["engine_time"], driver=call.data.get("driver"),
            passenger=call.data.get("passenger"), seat_time=call.data["seat_time"],
            climate_enabled=call.data["climate_enabled"],
        )

    if not hass.services.has_service(DOMAIN, "start_with_comfort"):
        hass.services.async_register(DOMAIN, "start_with_comfort", handle_comfort_start, schema=vol.Schema({
            vol.Optional("entry_id"): str,
            vol.Required("temperature"): vol.All(int, vol.Range(min=16, max=32)),
            vol.Optional("climate_enabled", default=True): bool,
            vol.Optional("climate_time", default=15): vol.All(int, vol.Range(min=5, max=30)),
            vol.Optional("engine_time", default=15): vol.All(int, vol.Range(min=1, max=30)),
            vol.Optional("seat_time", default=5): vol.All(int, vol.Range(min=1, max=10)),
            vol.Optional("driver"): vol.All(int, vol.Range(min=0, max=3)),
            vol.Optional("passenger"): vol.All(int, vol.Range(min=0, max=3)),
        }))

    async def handle_save_card_settings(call: ServiceCall) -> None:
        await select_coordinator(call).async_save_card_settings(call.data["settings"])

    if not hass.services.has_service(DOMAIN, "save_card_settings"):
        hass.services.async_register(DOMAIN, "save_card_settings", handle_save_card_settings, schema=vol.Schema({
            vol.Required("entry_id"): str,
            vol.Required("settings"): dict,
        }))

    async def handle_profile(call: ServiceCall) -> None:
        await select_coordinator(call).async_manage_profile(
            call.data["action"], profile_id=call.data.get("profile_id", ""),
            name=call.data.get("name", ""), settings=call.data.get("settings"),
        )

    if not hass.services.has_service(DOMAIN, "manage_preparation_profile"):
        hass.services.async_register(DOMAIN, "manage_preparation_profile", handle_profile, schema=vol.Schema({
            vol.Required("entry_id"): str,
            vol.Required("action"): vol.In(["create", "update", "copy", "delete", "select"]),
            vol.Optional("profile_id"): str,
            vol.Optional("name"): str,
            vol.Optional("settings"): dict,
        }))

    async def handle_command(call: ServiceCall) -> None:
        coordinators = _coordinators(hass)
        if not coordinators:
            return
        coordinator = select_coordinator(call)
        operation_time = call.data.get("operation_time")
        await coordinator.async_execute_command(
            call.service,
            operation_time=int(operation_time) if operation_time is not None else None,
        )

    async def handle_capture_marker(call: ServiceCall) -> None:
        coordinators = _coordinators(hass)
        if not coordinators:
            return
        label = call.data.get("label")
        await coordinators[0].async_add_protocol_capture_marker(str(label or ""))

    for command_key in COMMANDS:
        if not hass.services.has_service(DOMAIN, command_key):
            hass.services.async_register(DOMAIN, command_key, handle_command)

    if not hass.services.has_service(DOMAIN, SERVICE_ADD_CAPTURE_MARKER):
        hass.services.async_register(DOMAIN, SERVICE_ADD_CAPTURE_MARKER, handle_capture_marker)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        if not _coordinators(hass):
            for command_key in (*COMMANDS, "set_seat_heating", "start_with_comfort", "save_card_settings", "manage_preparation_profile"):
                if hass.services.has_service(DOMAIN, command_key):
                    hass.services.async_remove(DOMAIN, command_key)
            if hass.services.has_service(DOMAIN, SERVICE_ADD_CAPTURE_MARKER):
                hass.services.async_remove(DOMAIN, SERVICE_ADD_CAPTURE_MARKER)
    return unload_ok
