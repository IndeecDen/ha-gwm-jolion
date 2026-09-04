"""Button platform for GWM Jolion."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .commands import COMMANDS
from .const import DOMAIN
from .coordinator import GwmJolionCoordinator
from .entity import GwmJolionEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: GwmJolionCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[ButtonEntity] = [GwmJolionRefreshButton(coordinator)]
    if coordinator.enable_remote_controls and coordinator.security_pin:
        entities.extend(GwmJolionCommandButton(coordinator, command) for command in COMMANDS.values())
    async_add_entities(entities)


class GwmJolionRefreshButton(GwmJolionEntity, ButtonEntity):
    _attr_name = "Обновить данные"
    _attr_icon = "mdi:refresh"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: GwmJolionCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_refresh"

    async def async_press(self) -> None:
        await self.coordinator.async_request_refresh()


class GwmJolionCommandButton(GwmJolionEntity, ButtonEntity):
    def __init__(self, coordinator: GwmJolionCoordinator, command: dict) -> None:
        super().__init__(coordinator)
        self._command = command
        self._attr_unique_id = f"{coordinator.entry_id}_cmd_{command['key']}"
        self._attr_name = command["name"]
        self._attr_icon = command["icon"]
        self._attr_entity_registry_enabled_default = not bool(command.get("experimental"))

    async def async_press(self) -> None:
        await self.coordinator.async_execute_command(self._command["key"])
