"""Independent, read-only location polling."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
import time

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import GwmJolionApiError
from .const import MIN_GPS_INTERVAL, PUSH_FRESH_MS

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

    def _push_suppresses_poll(self, history, health):
        """Skip the cloud request while the head unit itself is streaming fresh fixes.

        The app pushes through our own HTTP view, so a recent acknowledged batch means
        the cloud copy cannot be newer; polling it only burns quota and quota-limited
        requests. Any push gap falls back to normal polling on the next tick.
        """
        if not getattr(history, "enabled", False) or not history.latest:
            return False
        if history.latest.get("source") != "app":
            return False
        last_ms = getattr(history, "last_received_ms", None)
        if not last_ms or abs(time.time() * 1000 - last_ms) > PUSH_FRESH_MS:
            return False
        health["push_polls_skipped"] = health.get("push_polls_skipped", 0) + 1
        health["push_last_skip"] = time.time()
        self.update_interval = timedelta(seconds=self.poll_interval)
        return True

    async def _async_update_data(self):
        local_history = getattr(self.parent, "trip_history", None)
        if getattr(local_history, "enabled", False) and not self.parent.data.get("vin"):
            return {**self.parent.data, "location": local_history.location()}
        health = getattr(self.parent, "gps_update_health", None)
        if health is None:
            health = self.parent.gps_update_health = {"consecutive_failures": 0}
        # Push-first: a batch acknowledged moments ago is newer than anything the cloud
        # can return, so polling would only spend rate limit. Any gap in pushes, or a
        # cloud-sourced newest fix, falls through to the normal request below.
        if getattr(local_history, "enabled", False) and local_history.latest:
            last_ms = getattr(local_history, "last_received_ms", None)
            if (local_history.latest.get("source") == "app" and last_ms
                    and abs(time.time() * 1000 - last_ms) <= PUSH_FRESH_MS):
                health["push_polls_skipped"] = health.get("push_polls_skipped", 0) + 1
                health["push_last_skip"] = time.time()
                self.update_interval = timedelta(seconds=self.poll_interval)
                return {**self.parent.data, "location": local_history.location()}
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
