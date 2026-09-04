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
from .commands import COMMANDS
from .const import (
    CONF_COMMAND_COOLDOWN, CONF_COUNTRY, CONF_COUNTRY_CODE, CONF_DEVICE_ID,
    CONF_ENABLE_REMOTE_CONTROLS, CONF_PHONE, CONF_POLL_INTERVAL, CONF_SECURITY_PIN,
    DEFAULT_COMMAND_COOLDOWN, DEFAULT_COUNTRY, DEFAULT_COUNTRY_CODE,
    DEFAULT_ENABLE_REMOTE_CONTROLS, DEFAULT_POLL_INTERVAL, DOMAIN, PLATFORMS,
)
from .coordinator import GwmJolionCoordinator

_LOGGER = logging.getLogger(__name__)

FRONTEND_FILE = Path(__file__).parent / "frontend" / "gwm-jolion-card.js"
FRONTEND_URL = "/gwm-jolion/gwm-jolion-card.js?v=0.1.0-alpha.6"
FRONTEND_STATIC_URL = "/gwm-jolion/gwm-jolion-card.js"
DATA_FRONTEND_REGISTERED = "_frontend_registered"


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
    coordinator = GwmJolionCoordinator(
        hass,
        client,
        int(options.get(CONF_POLL_INTERVAL, data.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL))),
        entry.entry_id,
        enable_remote_controls=bool(options.get(CONF_ENABLE_REMOTE_CONTROLS, DEFAULT_ENABLE_REMOTE_CONTROLS)),
        command_cooldown=int(options.get(CONF_COMMAND_COOLDOWN, DEFAULT_COMMAND_COOLDOWN)),
        security_pin=str(options.get(CONF_SECURITY_PIN)) if options.get(CONF_SECURITY_PIN) else None,
    )
    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _register_services(hass)
    return True


async def _async_register_frontend(hass: HomeAssistant) -> None:
    """Serve and load the bundled Lovelace card once per HA process."""
    if hass.data[DOMAIN].get(DATA_FRONTEND_REGISTERED):
        return

    if not FRONTEND_FILE.exists():
        _LOGGER.warning("Bundled GWM Jolion card was not found at %s", FRONTEND_FILE)
        return

    await hass.http.async_register_static_paths(
        [StaticPathConfig(FRONTEND_STATIC_URL, str(FRONTEND_FILE), False)]
    )
    frontend.add_extra_js_url(hass, FRONTEND_URL)
    hass.data[DOMAIN][DATA_FRONTEND_REGISTERED] = True
    _LOGGER.debug("Registered bundled GWM Jolion card at %s", FRONTEND_URL)


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

    for command_key in COMMANDS:
        if not hass.services.has_service(DOMAIN, command_key):
            hass.services.async_register(DOMAIN, command_key, handle_command)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        if not _coordinators(hass):
            for command_key in COMMANDS:
                if hass.services.has_service(DOMAIN, command_key):
                    hass.services.async_remove(DOMAIN, command_key)
    return unload_ok
