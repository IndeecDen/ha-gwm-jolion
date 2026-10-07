"""Sensor platform for the curated GWM Jolion entity surface."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

from .capabilities import capability_for_state_key
from .const import DOMAIN, EXTRA_SENSORS, ITEM_MAP, RAW_SENSOR_MAP
from .coordinator import GwmJolionCoordinator
from .entity import GwmJolionEntity
from .entity_surface import PUBLIC_EXTRA_SENSOR_KEYS, PUBLIC_RAW_SENSOR_CODES
from .health import snapshot


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
    entities.extend(GwmJolionHealthSensor(coordinator, key, name, icon) for key, name, icon in (
        ("cloud_status", "Связь с облаком GWM", "mdi:cloud-check"),
        ("location_source", "Источник координат", "mdi:map-marker-check"),
        ("locator_last_received", "Последние точки Locator", "mdi:map-marker-clock"),
    ))
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

    @property
    def available(self):
        return True


class GwmJolionHealthSensor(GwmJolionEntity, SensorEntity):
    """Health remains readable when the cloud is unavailable."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, key, name, icon):
        super().__init__(coordinator)
        self.key = key
        self._attr_unique_id = f"{coordinator.entry_id}_health_{key}"
        self._attr_name = name
        self._attr_icon = icon
        if key == "locator_last_received":
            self._attr_device_class = SensorDeviceClass.TIMESTAMP

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        # Age advances even when no cloud update or Locator point arrives.
        self.async_on_remove(async_track_time_interval(self.hass, self._tick, timedelta(seconds=30)))

    async def _tick(self, _now):
        self.async_write_ha_state()

    @property
    def available(self):
        return True

    @property
    def native_value(self):
        value = snapshot(self.coordinator)[self.key]
        return datetime.fromisoformat(value) if value and self.key == "locator_last_received" else value

    @property
    def extra_state_attributes(self):
        health = snapshot(self.coordinator)
        prefix = {"cloud_status": "cloud_", "location_source": "location_", "locator_last_received": "locator_"}[self.key]
        return {key: value for key, value in health.items() if key.startswith(prefix) and key != self.key}
