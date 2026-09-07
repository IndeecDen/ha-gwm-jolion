"""Button platform for GWM Jolion."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .commands import COMMANDS
from .const import DOMAIN
from .coordinator import GwmJolionCoordinator
from .entity import GwmJolionEntity
from .entity_surface import PUBLIC_COMMAND_BUTTON_KEYS


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: GwmJolionCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[ButtonEntity] = [GwmJolionRefreshButton(coordinator)]
    if coordinator.enable_remote_controls and coordinator.security_pin:
        entities.extend(
            GwmJolionCommandButton(coordinator, COMMANDS[key])
            for key in PUBLIC_COMMAND_BUTTON_KEYS
            if key in COMMANDS and coordinator.command_enabled(key)
        )
    async_add_entities(entities)


class GwmJolionRefreshButton(GwmJolionEntity, ButtonEntity):
    """Manual refresh plus compact operational diagnostics in attributes."""

    _attr_name = "Обновить данные"
    _attr_icon = "mdi:refresh"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: GwmJolionCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_refresh"

    async def async_press(self) -> None:
        await self.coordinator.async_request_refresh_with_source("manual_button")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        capture_path = self.coordinator.protocol_capture_path
        last_update = self.coordinator.last_successful_update
        last_capture = self.coordinator.protocol_capture_last_record_time
        return {
            "last_successful_update": last_update.isoformat() if last_update else None,
            "command_in_progress": self.coordinator.command_in_progress,
            "last_command_name": self.coordinator.last_command_name,
            "last_command_status": self.coordinator.last_command_status,
            "last_command_result_code": self.coordinator.last_command_result_code,
            "last_command_result_message": self.coordinator.last_command_result_message,
            "protocol_capture_enabled": self.coordinator.protocol_capture_enabled,
            "protocol_capture_file": Path(capture_path).name if capture_path else None,
            "protocol_capture_records": self.coordinator.protocol_capture_sequence,
            "protocol_capture_last_record": last_capture.isoformat() if last_capture else None,
            "protocol_capture_last_marker": self.coordinator.protocol_capture_last_marker,
            "protocol_capture_last_error": self.coordinator.protocol_capture_last_error,
        }


class GwmJolionCommandButton(GwmJolionEntity, ButtonEntity):
    def __init__(self, coordinator: GwmJolionCoordinator, command: dict) -> None:
        super().__init__(coordinator)
        self._command = command
        self._attr_unique_id = f"{coordinator.entry_id}_cmd_{command['key']}"
        self._attr_name = command["name"]
        self._attr_icon = command["icon"]

    async def async_press(self) -> None:
        await self.coordinator.async_execute_command(self._command["key"])
