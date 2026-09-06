"""GPS tracker for GWM Jolion."""

from __future__ import annotations

from typing import Any

from homeassistant.components.device_tracker import TrackerEntity
from homeassistant.components.device_tracker.const import SourceType
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import GwmJolionCoordinator
from .entity import GwmJolionEntity


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
    async_add_entities([GwmJolionLocationTracker(coordinator)])


class GwmJolionLocationTracker(GwmJolionEntity, TrackerEntity):
    _attr_name = "Местоположение"
    _attr_source_type = SourceType.GPS
    _attr_icon = "mdi:car"

    def __init__(self, coordinator: GwmJolionCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_location"

    @property
    def latitude(self) -> float | None:
        return _coordinate((self.coordinator.data.get("location") or {}).get("latitude"))

    @property
    def longitude(self) -> float | None:
        return _coordinate((self.coordinator.data.get("location") or {}).get("longitude"))

    @property
    def location_accuracy(self) -> int | None:
        return (self.coordinator.data.get("location") or {}).get("gps_accuracy")
