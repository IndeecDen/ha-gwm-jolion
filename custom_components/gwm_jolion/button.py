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
        entities.append(GwmJolionStartSelectedProfileButton(coordinator))
        entities.extend(
            GwmJolionCommandButton(coordinator, COMMANDS[key])
            for key in PUBLIC_COMMAND_BUTTON_KEYS
            if key in COMMANDS and coordinator.command_enabled(key)
        )
    async_add_entities(entities)
    if coordinator.enable_remote_controls and coordinator.security_pin:
        known_profiles: set[str] = set()

        def add_profile_buttons() -> None:
            new_profiles = [p for p in coordinator.preparation_profiles if p["id"] not in known_profiles]
            if new_profiles:
                known_profiles.update(p["id"] for p in new_profiles)
                async_add_entities([GwmJolionStartSelectedProfileButton(coordinator, profile_id=p["id"])
                                    for p in new_profiles])

        entry.async_on_unload(coordinator.async_add_listener(add_profile_buttons))
        add_profile_buttons()


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
            "card_settings": dict(self.coordinator.card_settings),
            "preparation_profiles": self.coordinator.preparation_profiles,
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


class GwmJolionStartSelectedProfileButton(GwmJolionEntity, ButtonEntity):
    """Automation-friendly entry point using the selected profile of this vehicle."""

    _attr_name = "Запустить выбранный профиль"
    _attr_icon = "mdi:car-clock"

    def __init__(self, coordinator: GwmJolionCoordinator, *, profile_id: str | None = None) -> None:
        super().__init__(coordinator)
        self._profile_id = profile_id
        self._attr_unique_id = (f"{coordinator.entry_id}_start_profile_{profile_id}" if profile_id is not None
                                else f"{coordinator.entry_id}_start_selected_profile")

    @property
    def profile_id(self) -> str | None:
        return self._profile_id if self._profile_id is not None else self.coordinator.card_settings.get("selected_profile")

    @property
    def name(self) -> str:
        if self._profile_id is None:
            return self._attr_name
        profile = next((p for p in self.coordinator.preparation_profiles if p["id"] == self._profile_id), None)
        return f"Запустить профиль: {profile['name']}" if profile else "Запустить профиль: удалён"

    @property
    def available(self) -> bool:
        return bool(super().available and self.coordinator.enable_remote_controls
                    and self.coordinator.security_pin and not self.coordinator.command_in_progress
                    and any(p["id"] == self.profile_id
                            for p in self.coordinator.preparation_profiles))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        selected = self.profile_id
        profile = next((p for p in self.coordinator.preparation_profiles if p["id"] == selected), None)
        return {"selected_profile_id": selected or None,
                "selected_profile_name": profile["name"] if profile else None}

    async def async_press(self) -> None:
        if self._profile_id is None:
            await self.coordinator.async_start_selected_profile()
        else:
            await self.coordinator.async_start_selected_profile(profile_id=self._profile_id)


class GwmJolionCommandButton(GwmJolionEntity, ButtonEntity):
    def __init__(self, coordinator: GwmJolionCoordinator, command: dict) -> None:
        super().__init__(coordinator)
        self._command = command
        self._attr_unique_id = f"{coordinator.entry_id}_cmd_{command['key']}"
        self._attr_name = command["name"]
        self._attr_icon = command["icon"]

    async def async_press(self) -> None:
        await self.coordinator.async_execute_command(self._command["key"])
