"""Central lock entity for GWM Jolion."""

from __future__ import annotations

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import GwmJolionCoordinator
from .entity import GwmJolionEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: GwmJolionCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([GwmJolionCentralLock(coordinator)])


class GwmJolionCentralLock(GwmJolionEntity, LockEntity):
    _attr_name = "Центральный замок"

    def __init__(self, coordinator: GwmJolionCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_central_lock"

    @property
    def is_locked(self) -> bool | None:
        unlocked = (self.coordinator.data.get("state") or {}).get("vehicle_unlocked")
        if not isinstance(unlocked, bool):
            return None
        return not unlocked

    async def async_lock(self, **kwargs) -> None:
        await self.coordinator.async_execute_command("lock_vehicle")

    async def async_unlock(self, **kwargs) -> None:
        await self.coordinator.async_execute_command("unlock_vehicle")
