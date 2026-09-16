"""Independent, read-only location polling."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
import time

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import GwmJolionApiError

_LOGGER = logging.getLogger(__name__)


class GwmGpsCoordinator(DataUpdateCoordinator):
    """Poll only the status endpoint; leave full telemetry and its health alone."""

    def __init__(self, parent, interval: int):
        super().__init__(parent.hass, _LOGGER, name="gwm_jolion_gps",
                         update_interval=timedelta(seconds=interval))
        self.parent = parent
        self.entry_id = parent.entry_id
        # Reuse the initial full refresh without issuing a duplicate request.
        self.async_set_updated_data(dict(parent.data))

    async def _async_update_data(self):
        try:
            async with asyncio.timeout(60):
                location = await self.parent.client.async_get_location(self.parent.data["vin"])
        except ConfigEntryAuthFailed:
            raise
        except (GwmJolionApiError, TimeoutError) as err:
            raise UpdateFailed(
                f"GPS update failed ({getattr(err, 'category', None) or type(err).__name__}, "
                f"code={getattr(err, 'code', None) or 'unknown'})"
            ) from err
        history = getattr(self.parent, "trip_history", None)
        if history:
            try:
                await history.append(time.time(), location)
            except Exception:
                _LOGGER.warning("Unable to save GWM trip observation; GPS update remains available")
        return {**self.parent.data, "location": location}
