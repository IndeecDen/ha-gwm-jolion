"""Authenticated trip history access scoped to the selected tracker."""
import logging

import voluptuous as vol
from homeassistant.auth.permissions.const import POLICY_READ
from homeassistant.components import websocket_api
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@callback
def register(hass):
    if hass.data[DOMAIN].get("_trips_ws"):
        return
    websocket_api.async_register_command(hass, get_trips)
    hass.data[DOMAIN]["_trips_ws"] = True


@websocket_api.websocket_command({
    vol.Required("type"): "gwm_jolion/trips",
    vol.Required("entity_id"): str,
    vol.Required("start"): str,
    vol.Required("end"): str,
})
@websocket_api.async_response
async def get_trips(hass, connection, msg):
    entity_id = msg["entity_id"]
    if not connection.user.permissions.check_entity(entity_id, POLICY_READ):
        connection.send_error(msg["id"], "unauthorized", "Нет доступа к автомобилю")
        return
    entry = er.async_get(hass).async_get(entity_id)
    parent = hass.data[DOMAIN].get(entry.config_entry_id) if entry else None
    if not entry or entry.platform != DOMAIN or not entity_id.startswith("device_tracker.") or not getattr(parent, "trip_history", None):
        connection.send_error(msg["id"], "not_found", "Выберите местоположение автомобиля GWM Jolion")
        return
    try:
        result = await parent.trip_history.query(msg["start"], msg["end"], hass.config.time_zone)
    except ValueError:
        connection.send_error(msg["id"], "invalid_dates", "Проверьте даты: максимальный период 366 дней")
    except Exception:
        _LOGGER.warning("Unable to read local GWM trip history")
        connection.send_error(msg["id"], "history_unavailable", "История поездок временно недоступна")
    else:
        connection.send_result(msg["id"], result)
