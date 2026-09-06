"""Sensors for GWM Jolion."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .capabilities import capability_for_state_key
from .const import DOMAIN, EXTRA_SENSORS, ITEM_MAP, RAW_SENSOR_MAP
from .coordinator import GwmJolionCoordinator
from .entity import GwmJolionEntity


@dataclass(frozen=True, kw_only=True)
class GwmJolionSensorDescription(SensorEntityDescription):
    state_key: str


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: GwmJolionCoordinator = hass.data[DOMAIN][entry.entry_id]
    descriptions: list[GwmJolionSensorDescription] = []
    for defn in list(ITEM_MAP.values()) + list(RAW_SENSOR_MAP.values()) + list(EXTRA_SENSORS.values()):
        capability = capability_for_state_key(defn.key)
        if capability is not None and not coordinator.feature_enabled(capability):
            continue
        descriptions.append(
            GwmJolionSensorDescription(
                key=defn.key,
                state_key=defn.key,
                name=defn.name,
                native_unit_of_measurement=defn.unit,
                icon=defn.icon,
                device_class=defn.device_class,
                entity_category=EntityCategory.DIAGNOSTIC if defn.diagnostic else None,
            )
        )
    entities: list[SensorEntity] = [GwmJolionSensor(coordinator, d) for d in descriptions]
    entities.extend(
        [
            GwmJolionLastCommandSensor(coordinator),
            GwmJolionLastCommandTimeSensor(coordinator),
            GwmJolionLastUpdateSensor(coordinator),
            GwmJolionUnknownSignalsSensor(coordinator),
            GwmJolionVehicleBasicsStatusSensor(coordinator),
            GwmJolionFeatureFlagsSensor(coordinator),
            GwmJolionProtocolCaptureSensor(coordinator),
        ]
    )
    async_add_entities(entities)


class GwmJolionSensor(GwmJolionEntity, SensorEntity):
    entity_description: GwmJolionSensorDescription

    def __init__(self, coordinator: GwmJolionCoordinator, description: GwmJolionSensorDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.entry_id}_{description.key}"

    @property
    def native_value(self) -> Any:
        return (self.coordinator.data.get("state") or {}).get(self.entity_description.state_key)


class GwmJolionLastCommandSensor(GwmJolionEntity, SensorEntity):
    _attr_name = "Последняя удалённая команда"
    _attr_icon = "mdi:cloud-check"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: GwmJolionCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_last_command"

    @property
    def native_value(self) -> str | None:
        name = self.coordinator.last_command_name
        if name is None:
            return None
        status = self.coordinator.last_command_status
        suffix = {
            "pending": "выполняется",
            "success": "выполнено",
            "error": "ошибка",
        }.get(status)
        return name if not suffix else f"{name} — {suffix}"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "status": self.coordinator.last_command_status,
            "result_code": self.coordinator.last_command_result_code,
            "result_message": self.coordinator.last_command_result_message,
            "in_progress": self.coordinator.command_in_progress,
        }


class GwmJolionLastCommandTimeSensor(GwmJolionEntity, SensorEntity):
    _attr_name = "Время последней команды"
    _attr_icon = "mdi:clock-outline"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: GwmJolionCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_last_command_time"

    @property
    def native_value(self) -> datetime | None:
        return self.coordinator.last_command_at


class GwmJolionLastUpdateSensor(GwmJolionEntity, SensorEntity):
    _attr_name = "Последнее обновление GWM"
    _attr_icon = "mdi:cloud-sync"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: GwmJolionCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_last_successful_update"

    @property
    def native_value(self) -> datetime | None:
        return self.coordinator.last_successful_update


class GwmJolionUnknownSignalsSensor(GwmJolionEntity, SensorEntity):
    _attr_name = "Неизвестные GWM-коды"
    _attr_icon = "mdi:code-braces"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: GwmJolionCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_unknown_signal_count"

    @property
    def native_value(self) -> int:
        return len(self.coordinator.unknown_signal_history)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "codes": sorted(self.coordinator.unknown_signal_history),
            "seen_signal_count": len(self.coordinator.seen_signal_codes),
        }


class GwmJolionVehicleBasicsStatusSensor(GwmJolionEntity, SensorEntity):
    _attr_name = "vehicleBasicsInfo"
    _attr_icon = "mdi:cloud-question"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: GwmJolionCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_vehicle_basics_status"

    @property
    def native_value(self) -> str | None:
        diagnostics = (self.coordinator.data or {}).get("vehicle_basics_diagnostics") or {}
        return diagnostics.get("status")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        diagnostics = (self.coordinator.data or {}).get("vehicle_basics_diagnostics") or {}
        return {
            "response_code": diagnostics.get("response_code"),
            "description": diagnostics.get("description"),
            "data_type": diagnostics.get("data_type"),
        }


class GwmJolionFeatureFlagsSensor(GwmJolionEntity, SensorEntity):
    """Expose manual equipment flags to diagnostics and the bundled card."""

    _attr_name = "Оборудование автомобиля"
    _attr_icon = "mdi:car-cog"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: GwmJolionCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_feature_flags"

    @property
    def native_value(self) -> str:
        return "configured"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return dict(self.coordinator.feature_flags)


class GwmJolionProtocolCaptureSensor(GwmJolionEntity, SensorEntity):
    """Expose whether field-test protocol capture is healthy and recording."""

    _attr_name = "Запись протокола GWM"
    _attr_icon = "mdi:file-document-edit-outline"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: GwmJolionCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_protocol_capture_status"

    @property
    def native_value(self) -> str:
        if not self.coordinator.protocol_capture_enabled:
            return "disabled"
        if self.coordinator.protocol_capture_last_error:
            return "error"
        return "recording"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        path = self.coordinator.protocol_capture_path
        last_time = self.coordinator.protocol_capture_last_record_time
        return {
            "file_name": Path(path).name if path else None,
            "records_written": self.coordinator.protocol_capture_sequence,
            "last_record_time": last_time.isoformat() if last_time else None,
            "last_source": self.coordinator.protocol_capture_last_source,
            "last_changes_count": self.coordinator.protocol_capture_last_changes_count,
            "last_marker": self.coordinator.protocol_capture_last_marker,
            "last_error": self.coordinator.protocol_capture_last_error,
        }
