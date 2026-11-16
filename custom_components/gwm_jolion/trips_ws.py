"""Authenticated trip history access scoped to the selected tracker."""
import logging
import asyncio
import time

import voluptuous as vol
from homeassistant.auth.permissions.const import POLICY_READ
from homeassistant.components import websocket_api
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .trips_recorder import read_history

_LOGGER = logging.getLogger(__name__)

RECORDER_TIMEOUT = 10

# Two dashboards (or two open tabs) can ask for the same window in the same second.
# The Recorder read is the slowest phase of a trip request, so identical concurrent
# reads share one query instead of queueing behind each other. The entry is dropped
# as soon as the shared read finishes: nothing is ever served from a stored result.
_INFLIGHT: dict[tuple, "asyncio.Future"] = {}

# A window that ended before today cannot gain new Recorder rows, yet the card
# asks for the same days every time the dashboard opens and switching between
# two days re-reads both. Caching the finished answer takes the week-long
# Recorder read off that path; the window that includes today is never cached.
_RESULT_CACHE: dict[tuple, tuple[float, dict]] = {}
_RESULT_CACHE_TTL = 300.0
_RESULT_CACHE_MAX = 4


def _closed_window(hass, end):
    """True when the window ended before today, so its rows can no longer change."""
    last = dt_util.parse_date(end)
    if last is None:
        return False
    zone = hass.config.time_zone
    # Home Assistant keeps the zone as a name like "Europe/Moscow"; dt_util.now() wants a tzinfo.
    tz = dt_util.get_time_zone(zone) if isinstance(zone, str) else zone
    return last < dt_util.now(tz).date()


async def _timed_recorder_read(reader, hass, entity_id, odometer, start, end, engine):
    """Run one Recorder read under a hard timeout, shared by every waiter of it."""
    async with asyncio.timeout(RECORDER_TIMEOUT):
        return await reader(hass, entity_id, odometer, start, end, engine)


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
        request_started = time.perf_counter()
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
        cached_result = None
        cache_key = None
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
            if _closed_window(hass, msg["end"]):
                cache_key = (entity_id, msg["start"], msg["end"], odometer, engine, include_app, include_cloud)
                stored = _RESULT_CACHE.get(cache_key)
                if stored is not None and time.perf_counter() - stored[0] < _RESULT_CACHE_TTL:
                    cached_result = dict(stored[1])
            recorder_started = time.perf_counter()
            try:
                if cached_result is None:
                    # Same window asked for twice at once: share the read that is
                    # already running instead of queueing a second Recorder query.
                    key = (entity_id, msg["start"], msg["end"], odometer, engine)
                    task = _INFLIGHT.get(key)
                    if task is None or task.done():
                        task = asyncio.ensure_future(
                            _timed_recorder_read(read_history, hass, entity_id, odometer, msg["start"], msg["end"], engine)
                        )
                        _INFLIGHT[key] = task
                        task.add_done_callback(lambda _task, _key=key: _INFLIGHT.pop(_key, None))
                    archive = await task
            except ValueError:
                raise
            except Exception:
                recorder_error = True
                _LOGGER.warning("Recorder history unavailable; using local trip history")
            finally:
                recorder_ms = round((time.perf_counter() - recorder_started) * 1000)
        processing_started = time.perf_counter()
        if cached_result is not None:
            result = cached_result
        elif archive is None:
            result = await parent.trip_history.query(msg["start"], msg["end"], hass.config.time_zone, **sources)
        else:
            if len(archive) == 3:
                gps, mileage, _engines = archive
                archive = (gps, mileage)
            result = await parent.trip_history.query(msg["start"], msg["end"], hass.config.time_zone, archive, **sources)
        result["selected_sources"] = {"app": include_app, "cloud": include_cloud}
        processing_ms = round((time.perf_counter() - processing_started) * 1000)
        if cache_key is not None and cached_result is None:
            _RESULT_CACHE[cache_key] = (time.perf_counter(), dict(result))
            while len(_RESULT_CACHE) > _RESULT_CACHE_MAX:
                _RESULT_CACHE.pop(next(iter(_RESULT_CACHE)), None)
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
                "total_ms": round((time.perf_counter() - request_started) * 1000),
                "cached": cached_result is not None,
            }
    except ValueError:
        connection.send_error(msg["id"], "invalid_dates", "Проверьте даты: максимальный период 366 дней")
    except Exception:
        _LOGGER.warning("Unable to read local GWM trip history", exc_info=True)
        connection.send_error(msg["id"], "history_unavailable", "История поездок временно недоступна")
    else:
        connection.send_result(msg["id"], result)
