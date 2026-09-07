"""Sensor platform for the curated GWM Jolion entity surface."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .capabilities import capability_for_state_key
from .const import DOMAIN, EXTRA_SENSORS, ITEM_MAP, RAW_SENSOR_MAP
from .coordinator import GwmJolionCoordinator
from .entity import GwmJolionEntity
from .entity_surface import PUBLIC_EXTRA_SENSOR_KEYS, PUBLIC_RAW_SENSOR_CODES


@dataclass(frozen=True, kw_only=True)
class GwmJolionSensorDescription(SensorEntityDescription):
    state_key: str


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: GwmJolionCoordinator = hass.data[DOMAIN][entry.entry_id]

    public_defs = list(ITEM_MAP.values())
    public_defs.extend(RAW_SENSOR_MAP[code] for code in PUBLIC_RAW_SENSOR_CODES)
    public_defs.extend(EXTRA_SENSORS[key] for key in PUBLIC_EXTRA_SENSOR_KEYS)

    descriptions: list[GwmJolionSensorDescription] = []
    for defn in public_defs:
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

    entities: list[SensorEntity] = [GwmJolionSensor(coordinator, description) for description in descriptions]
    entities.append(GwmJolionLastUpdateSensor(coordinator))
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


class GwmJolionLastUpdateSensor(GwmJolionEntity, SensorEntity):
    """Keep one useful diagnostic timestamp instead of a collection of helper sensors."""

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
