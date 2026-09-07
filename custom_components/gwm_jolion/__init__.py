"""GWM Jolion integration."""

from __future__ import annotations

import logging
from pathlib import Path
from uuid import uuid4

from homeassistant.components import frontend
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import GwmJolionApiClient
from .capabilities import resolve_manual_capabilities
from .commands import COMMANDS
from .const import (
    CONF_COMMAND_COOLDOWN, CONF_COUNTRY, CONF_COUNTRY_CODE, CONF_DEVICE_ID,
    CONF_ENABLE_REMOTE_CONTROLS, CONF_PHONE, CONF_POLL_INTERVAL, CONF_SECURITY_PIN,
    DEFAULT_COMMAND_COOLDOWN, DEFAULT_COUNTRY, DEFAULT_COUNTRY_CODE,
    DEFAULT_ENABLE_REMOTE_CONTROLS, DEFAULT_POLL_INTERVAL, DOMAIN, PLATFORMS,
)
from .coordinator import GwmJolionCoordinator
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
        "/gwm-jolion/gwm-jolion-card-editor.js?v=0.1.0-alpha.19.5",
    ),
    (
        FRONTEND_DIR / "gwm-jolion-card.js",
        "/gwm-jolion/gwm-jolion-card.js",
        "/gwm-jolion/gwm-jolion-card.js?v=0.1.0-alpha.19.5",
    ),
    (
        FRONTEND_DIR / "gwm-jolion-remote-card.js",
        "/gwm-jolion/gwm-jolion-remote-card.js",
        "/gwm-jolion/gwm-jolion-remote-card.js?v=0.1.0-alpha.19.5",
    ),
)
DATA_FRONTEND_REGISTERED = "_frontend_registered"
SERVICE_ADD_CAPTURE_MARKER = "add_capture_marker"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    await _async_register_frontend(hass)

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
    async def handle_command(call: ServiceCall) -> None:
        coordinators = _coordinators(hass)
        if not coordinators:
            return
        coordinator = coordinators[0]
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
            for command_key in COMMANDS:
                if hass.services.has_service(DOMAIN, command_key):
                    hass.services.async_remove(DOMAIN, command_key)
            if hass.services.has_service(DOMAIN, SERVICE_ADD_CAPTURE_MARKER):
                hass.services.async_remove(DOMAIN, SERVICE_ADD_CAPTURE_MARKER)
    return unload_ok
