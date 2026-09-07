"""Binary sensors for the curated GWM Jolion entity surface."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import BINARY_SENSOR_DEFS, DOMAIN
from .coordinator import GwmJolionCoordinator
from .entity import GwmJolionEntity


_RAW_STATE_BY_KEY: dict[str, str] = {
    "engine_running": "engine_state_raw",
    "door_front_left_open": "door_front_left_raw",
    "door_rear_left_open": "door_rear_left_raw",
    "door_front_right_open": "door_front_right_raw",
    "door_rear_right_open": "door_rear_right_raw",
    "window_2210001_open": "window_2210001_raw",
    "window_2210002_open": "window_2210002_raw",
    "window_2210003_open": "window_2210003_raw",
    "window_2210004_open": "window_2210004_raw",
    "trunk_open": "trunk_raw",
    "climate_on": "climate_raw",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: GwmJolionCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        GwmJolionBinarySensor(
            coordinator,
            key=key,
            name=name,
            device_class=device_class,
        )
        for key, name, device_class, _diagnostic in BINARY_SENSOR_DEFS
    )


class GwmJolionBinarySensor(GwmJolionEntity, BinarySensorEntity):
    def __init__(
        self,
        coordinator: GwmJolionCoordinator,
        *,
        key: str,
        name: str,
        device_class: str | None,
    ) -> None:
        super().__init__(coordinator)
        self._state_key = key
        self._attr_unique_id = f"{coordinator.entry_id}_{key}"
        self._attr_name = name
        self._attr_device_class = device_class

    @property
    def is_on(self) -> bool | None:
        value = (self.coordinator.data.get("state") or {}).get(self._state_key)
        return value if isinstance(value, bool) else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        state = (self.coordinator.data or {}).get("state") or {}
        attributes: dict[str, Any] = {}

        raw_key = _RAW_STATE_BY_KEY.get(self._state_key)
        if raw_key is not None:
            attributes["raw_state"] = state.get(raw_key)

        if self._state_key == "tbox_online":
            location = (self.coordinator.data or {}).get("location") or {}
            attributes.update(
                {
                    "signal_level_raw": state.get("tbox_signal_raw"),
                    "model_code_raw": state.get("model_code_raw"),
                    "oil_qty_raw": state.get("oil_qty"),
                    "gps_available": location.get("latitude") is not None and location.get("longitude") is not None,
                    "feature_flags": dict(self.coordinator.feature_flags),
                }
            )

        return attributes
