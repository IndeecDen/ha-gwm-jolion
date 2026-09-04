"""Binary sensors for GWM Jolion."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import BINARY_SENSOR_DEFS, DOMAIN
from .coordinator import GwmJolionCoordinator
from .entity import GwmJolionEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: GwmJolionCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        GwmJolionBinarySensor(coordinator, key=key, name=name, device_class=device_class, diagnostic=diagnostic)
        for key, name, device_class, diagnostic in BINARY_SENSOR_DEFS
    )


class GwmJolionBinarySensor(GwmJolionEntity, BinarySensorEntity):
    def __init__(self, coordinator: GwmJolionCoordinator, *, key: str, name: str, device_class: str | None, diagnostic: bool) -> None:
        super().__init__(coordinator)
        self._state_key = key
        self._attr_unique_id = f"{coordinator.entry_id}_{key}"
        self._attr_name = name
        self._attr_device_class = device_class
        if diagnostic:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def is_on(self) -> bool | None:
        value = (self.coordinator.data.get("state") or {}).get(self._state_key)
        return value if isinstance(value, bool) else None
