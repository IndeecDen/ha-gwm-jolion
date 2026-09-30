"""GPS tracker for GWM Jolion."""

from __future__ import annotations

from typing import Any

from homeassistant.components.device_tracker import TrackerEntity
from homeassistant.components.device_tracker.const import SourceType
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, CONF_GPS_INTERVAL, CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL, MIN_GPS_INTERVAL
from .gps import GwmGpsCoordinator
from .coordinator import GwmJolionCoordinator
from .entity import GwmJolionEntity
from .locator_protocol import accuracy_meters


def _coordinate(value: Any) -> float | None:
    """Return a numeric coordinate suitable for the Home Assistant map."""
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: GwmJolionCoordinator = hass.data[DOMAIN][entry.entry_id]
    interval = int(entry.options.get(CONF_GPS_INTERVAL, entry.options.get(
        CONF_POLL_INTERVAL, entry.data.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL))))
    gps = GwmGpsCoordinator(coordinator, max(MIN_GPS_INTERVAL, min(3600, interval)))
    # Keep recording when the map/entity is not currently displayed; detach on unload.
    entry.async_on_unload(gps.async_add_listener(lambda: None))
    async_add_entities([GwmJolionLocationTracker(gps)])


class GwmJolionLocationTracker(GwmJolionEntity, TrackerEntity):
    _attr_name = "Местоположение"
    _attr_source_type = SourceType.GPS
    _attr_icon = "mdi:car"

    def __init__(self, coordinator: GwmGpsCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_location"

    @property
    def available(self):
        history = getattr(self.coordinator.parent, "trip_history", None)
        if getattr(history, "enabled", False):
            return bool(history.latest)
        return super().available

    @property
    def latitude(self) -> float | None:
        return _coordinate((self.coordinator.data.get("location") or {}).get("latitude"))

    @property
    def longitude(self) -> float | None:
        return _coordinate((self.coordinator.data.get("location") or {}).get("longitude"))

    @property
    def location_accuracy(self) -> float:
        # Must never be None: Home Assistant passes this into zone matching, and
        # a None radius raises TypeError while writing the state, which drops the
        # entity entirely rather than just showing it as unavailable.
        return accuracy_meters((self.coordinator.data.get("location") or {}).get("gps_accuracy"))

    @property
    def extra_state_attributes(self):
        location = self.coordinator.data.get("location") or {}
        history = getattr(self.coordinator.parent, "trip_history", None)
        return {"golion_locator_enabled": bool(getattr(history, "enabled", False)),
                "locator_transport": ("yandex_disk" if getattr(history,"relay",None) else "https"),
                "locator_relay_status": getattr(getattr(history,"relay",None),"status",None),
                "location_source": location.get("source", "cloud"),
                "gps_timestamp_ms": location.get("gps_timestamp_ms"),
                "gps_time_known": location.get("time_known", False),
                "gps_accuracy_known": location.get("accuracy_known", False),
                "speed_kmh": location.get("speed_kmh"), "speed_accuracy_kmh": location.get("speed_accuracy_kmh"), "bearing": location.get("bearing")}
