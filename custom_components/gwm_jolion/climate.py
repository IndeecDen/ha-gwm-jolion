"""Remote climate entity for GWM Jolion."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import ClimateEntityFeature, HVACMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import GwmJolionApiError
from .const import DOMAIN, MAX_CLIMATE_TEMPERATURE, MIN_CLIMATE_TEMPERATURE
from .coordinator import GwmJolionCoordinator
from .entity import GwmJolionEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: GwmJolionCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([GwmJolionClimate(coordinator)])


class GwmJolionClimate(GwmJolionEntity, ClimateEntity):
    _attr_name = "Климат"
    _attr_icon = "mdi:car-defrost-front"
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT_COOL]
    _attr_min_temp = MIN_CLIMATE_TEMPERATURE
    _attr_max_temp = MAX_CLIMATE_TEMPERATURE
    _attr_target_temperature_step = 1
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    def __init__(self, coordinator: GwmJolionCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_climate"

    @property
    def hvac_mode(self) -> HVACMode | None:
        value = (self.coordinator.data.get("state") or {}).get("climate_on")
        if not isinstance(value, bool):
            return None
        return HVACMode.HEAT_COOL if value else HVACMode.OFF

    @property
    def target_temperature(self) -> float:
        return float(self.coordinator.climate_target_temperature)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        state = self.coordinator.data.get("state") or {}
        return {
            "operation_time_minutes": self.coordinator.climate_operation_time,
            "vehicle_climate_raw": state.get("climate_raw"),
            "saved_temperature_gwm": state.get("climate_saved_temperature"),
            "saved_runtime_gwm": state.get("climate_saved_runtime"),
        }

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode == HVACMode.OFF:
            await self.async_turn_off()
        elif hvac_mode == HVACMode.HEAT_COOL:
            await self.async_turn_on()
        else:
            raise HomeAssistantError(f"Unsupported HVAC mode: {hvac_mode}")

    async def async_set_temperature(self, **kwargs: Any) -> None:
        value = kwargs.get(ATTR_TEMPERATURE)
        if value is None:
            return
        temperature = int(round(float(value)))
        if not MIN_CLIMATE_TEMPERATURE <= temperature <= MAX_CLIMATE_TEMPERATURE:
            raise HomeAssistantError(f"Temperature must be {MIN_CLIMATE_TEMPERATURE}..{MAX_CLIMATE_TEMPERATURE} °C")
        self.coordinator.climate_target_temperature = temperature
        self.async_write_ha_state()
        if self.hvac_mode == HVACMode.HEAT_COOL:
            await self.async_turn_on()

    async def async_turn_on(self) -> None:
        await self._send_climate(enabled=True)

    async def async_turn_off(self) -> None:
        await self._send_climate(enabled=False)

    async def _send_climate(self, *, enabled: bool) -> None:
        vin = (self.coordinator.data or {}).get("vin")
        if not vin:
            raise HomeAssistantError("Vehicle VIN is not available")
        temperature = int(self.coordinator.climate_target_temperature)
        runtime = int(self.coordinator.climate_operation_time)

        if enabled:
            try:
                await self.coordinator.client.async_update_climate_defaults(str(vin), temperature, runtime)
            except GwmJolionApiError as err:
                _LOGGER.debug("Could not persist climate defaults: %s", err)

        instructions = {
            "0x04": {
                "airConditioner": {
                    "operationTime": str(runtime),
                    "switchOrder": "1" if enabled else "0",
                    "temperature": str(temperature),
                }
            }
        }
        await self.coordinator.async_send_custom_t5(
            name=f"Климат ON {temperature}°C / {runtime} мин" if enabled else "Климат OFF",
            instructions=instructions,
            expected_remote_type="0x04",
        )
