"""Number entities for GWM Jolion."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MAX_CLIMATE_RUNTIME, MIN_CLIMATE_RUNTIME
from .coordinator import GwmJolionCoordinator
from .entity import GwmJolionEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: GwmJolionCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([GwmJolionClimateRuntimeNumber(coordinator)])


class GwmJolionClimateRuntimeNumber(GwmJolionEntity, NumberEntity):
    _attr_name = "Время работы климата"
    _attr_icon = "mdi:timer-outline"
    _attr_native_min_value = MIN_CLIMATE_RUNTIME
    _attr_native_max_value = MAX_CLIMATE_RUNTIME
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "min"
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator: GwmJolionCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_climate_runtime"

    @property
    def native_value(self) -> float:
        return float(self.coordinator.climate_operation_time)

    async def async_set_native_value(self, value: float) -> None:
        self.coordinator.climate_operation_time = int(value)
        self.async_write_ha_state()
