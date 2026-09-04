"""Base entities for GWM Jolion."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import GwmJolionCoordinator


class GwmJolionEntity(CoordinatorEntity[GwmJolionCoordinator]):
    """Base GWM Jolion entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: GwmJolionCoordinator) -> None:
        super().__init__(coordinator)

    @property
    def device_info(self) -> DeviceInfo:
        data = self.coordinator.data or {}
        state = data.get("state") or {}
        vin = str(data.get("vin") or self.coordinator.entry_id)
        return DeviceInfo(
            identifiers={(DOMAIN, vin)},
            name=data.get("vehicle_name") or "Haval Jolion",
            manufacturer="GWM / Haval",
            model=str(state.get("model") or "Jolion"),
        )
