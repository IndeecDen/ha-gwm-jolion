"""Authenticated trip history access scoped to the selected tracker."""
import logging
import asyncio
import time

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
    vol.Optional("odometer_entity"): str,
    vol.Optional("skip_recorder", default=False): bool,
    vol.Optional("include_app", default=True): bool,
    vol.Optional("include_cloud", default=True): bool,
})
@websocket_api.async_response
async def get_trips(hass, connection, msg):
    # Keep the handler usable when a test harness extracts this function alone.
    clock = globals().get("perf_counter")
    logger = globals().get("_LOGGER")
    if clock is None:
        clock = time.perf_counter if "time" in globals() else __import__("time").perf_counter
    if logger is None:
        logger = logging.getLogger(__name__) if "logging" in globals() else type(
            "_Logger", (), {"warning": lambda self, *args: None}
        )()
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
        request_started = clock()
        recorder_ms = 0
        processing_ms = 0
        archive = None
        recorder_configured = "recorder" in getattr(hass.config, "components", set())
        include_app = msg.get("include_app", True)
        include_cloud = msg.get("include_cloud", True)
        sources = {} if include_app and include_cloud else {"include_app": include_app, "include_cloud": include_cloud}
        # GPS source selection is independent of Recorder mileage. Choosing only
        # Locator must still allow the selected odometer entity to provide km.
        skip_recorder = msg.get("skip_recorder", False)
        recorder_available = recorder_configured and not skip_recorder
        recorder_error = False
        if recorder_available:
            registry = er.async_get(hass)
            odometer = msg.get("odometer_entity") or registry.async_get_entity_id("sensor", DOMAIN, f"{entry.config_entry_id}_mileage_total")
            engine = registry.async_get_entity_id("binary_sensor", DOMAIN, f"{entry.config_entry_id}_engine_running")
            if odometer:
                sensor = registry.async_get(odometer)
                if (not sensor or sensor.platform != DOMAIN or sensor.config_entry_id != entry.config_entry_id
                        or not odometer.startswith("sensor.") or not connection.user.permissions.check_entity(odometer, POLICY_READ)):
                    connection.send_error(msg["id"], "unauthorized", "Нет доступа к выбранному датчику пробега этого автомобиля")
                    return
            reader = globals().get("read_history")
            if reader is None:
                try:
                    from .trips_recorder import read_history as reader
                except ImportError:
                    reader = None
            recorder_started = clock()
            try:
                if reader is not None:
                    async with asyncio.timeout(10):
                        archive = await reader(hass, entity_id, odometer, msg["start"], msg["end"], engine)
            except ValueError:
                raise
            except Exception:
                recorder_error = True
                logger.warning("Recorder history unavailable; using local trip history")
            finally:
                recorder_ms = round((clock() - recorder_started) * 1000)
        processing_started = clock()
        if archive is None:
            result = await parent.trip_history.query(msg["start"], msg["end"], hass.config.time_zone, **sources)
        else:
            if len(archive) == 3:
                gps, mileage, _engines = archive
                archive = (gps, mileage)
            result = await parent.trip_history.query(msg["start"], msg["end"], hass.config.time_zone, archive, **sources)
        result["selected_sources"] = {"app": include_app, "cloud": include_cloud}
        processing_ms = round((clock() - processing_started) * 1000)
        if "segments" in result or "source_counts" in result:
            history = parent.trip_history
            result["diagnostics"] = {
                "locator_enabled": bool(getattr(history, "enabled", False)),
                "recorder_available": recorder_available and not recorder_error,
                "recorder_configured": recorder_configured,
                "recorder_skipped": skip_recorder,
                "recorder_error": recorder_error,
                "retention_days": getattr(history, "retention", None),
                "source_counts": result.get("source_counts", {}),
            }
            result["server_timings"] = {
                "recorder_ms": recorder_ms,
                "history_processing_ms": processing_ms,
                "total_ms": round((clock() - request_started) * 1000),
            }
    except ValueError:
        connection.send_error(msg["id"], "invalid_dates", "Проверьте даты: максимальный период 366 дней")
    except Exception:
        logger.warning("Unable to read local GWM trip history", exc_info=True)
        connection.send_error(msg["id"], "history_unavailable", "История поездок временно недоступна")
    else:
        connection.send_result(msg["id"], result)
