"""Independent, read-only location polling."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
import time

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import GwmJolionApiError
from .const import MIN_GPS_INTERVAL

_LOGGER = logging.getLogger(__name__)


class GwmGpsCoordinator(DataUpdateCoordinator):
    """Poll only the status endpoint; leave full telemetry and its health alone."""

    def __init__(self, parent, interval: int):
        self.poll_interval = max(MIN_GPS_INTERVAL, min(3600, interval))
        super().__init__(parent.hass, _LOGGER, name="gwm_jolion_gps",
                         update_interval=timedelta(seconds=self.poll_interval),
                         config_entry=parent.config_entry)
        self.parent = parent
        self.entry_id = parent.entry_id
        history = getattr(parent, "trip_history", None)
        if getattr(history, "enabled", False):
            history.gps = self
        # Reuse the initial full refresh without issuing a duplicate request.
        self.async_set_updated_data(dict(parent.data))
        if getattr(history, "enabled", False):
            history.publish()

    async def _async_update_data(self):
        local_history = getattr(self.parent, "trip_history", None)
        if getattr(local_history, "enabled", False) and not self.parent.data.get("vin"):
            return {**self.parent.data, "location": local_history.location()}
        health = getattr(self.parent, "gps_update_health", None)
        if health is None:
            health = self.parent.gps_update_health = {"consecutive_failures": 0}
        try:
            async with asyncio.timeout(60):
                location = await self.parent.client.async_get_location(self.parent.data["vin"])
        except ConfigEntryAuthFailed:
            history = getattr(self.parent, "trip_history", None)
            if getattr(history, "enabled", False) and history.latest:
                return {**self.parent.data, "location": history.location()}
            raise
        except (GwmJolionApiError, TimeoutError) as err:
            health["consecutive_failures"] += 1
            delay = max(self.poll_interval, min(300, 30 * 2 ** min(health["consecutive_failures"] - 1, 4)))
            self.update_interval = timedelta(seconds=delay)
            health["effective_interval_seconds"] = delay
            health["last_error"] = {"code": getattr(err, "code", None), "category": getattr(err, "category", None) or type(err).__name__, "time": time.time()}
            history = getattr(self.parent, "trip_history", None)
            if getattr(history, "enabled", False) and history.latest:
                return {**self.parent.data, "location": history.location()}
            raise UpdateFailed(
                f"GPS update failed ({getattr(err, 'category', None) or type(err).__name__}, "
                f"code={getattr(err, 'code', None) or 'unknown'})"
            ) from err
        self.update_interval = timedelta(seconds=self.poll_interval)
        health["effective_interval_seconds"] = self.poll_interval
        health["consecutive_failures"] = 0
        health["last_success"] = time.time()
        history = getattr(self.parent, "trip_history", None)
        if history:
            try:
                await history.append(time.time(), location)
                health["history_write_failed"] = False
            except Exception:
                health["history_write_failed"] = True
                _LOGGER.warning("Unable to save GWM trip observation; GPS update remains available")
        if getattr(history, "enabled", False):
            location = history.location(location)
        return {**self.parent.data, "location": location}
