"""Capability metadata for GWM Jolion.

The capability framework is deliberately informational in alpha.3. It does not
change command availability yet; that will happen only after physical tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class CapabilityStatus(StrEnum):
    CONFIRMED = "confirmed"
    IMPLEMENTED = "implemented"
    EXPERIMENTAL = "experimental"
    DISCOVERED = "discovered"


@dataclass(frozen=True, slots=True)
class CapabilityDef:
    key: str
    name: str
    status: CapabilityStatus
    signal_codes: tuple[str, ...] = ()
    command_keys: tuple[str, ...] = ()


CAPABILITIES: dict[str, CapabilityDef] = {
    "engine": CapabilityDef("engine", "Удалённый запуск двигателя", CapabilityStatus.CONFIRMED, ("2016001",), ("start_engine", "stop_engine")),
    "central_lock": CapabilityDef("central_lock", "Центральный замок", CapabilityStatus.CONFIRMED, ("2208001",), ("lock_vehicle", "unlock_vehicle")),
    "trunk": CapabilityDef("trunk", "Багажник", CapabilityStatus.IMPLEMENTED, ("2206001",), ("open_trunk", "close_trunk")),
    "windows_close": CapabilityDef("windows_close", "Закрытие окон", CapabilityStatus.IMPLEMENTED, ("2210001", "2210002", "2210003", "2210004"), ("close_windows",)),
    "climate": CapabilityDef("climate", "Климат", CapabilityStatus.EXPERIMENTAL, ("2202001",), ()),
    "rear_defrost": CapabilityDef("rear_defrost", "Обогрев заднего стекла", CapabilityStatus.IMPLEMENTED, ("2210032",), ("rear_defrost_on", "rear_defrost_off")),
    "steering_wheel_heat": CapabilityDef("steering_wheel_heat", "Обогрев руля", CapabilityStatus.IMPLEMENTED, ("2060016",), ("steering_wheel_heat_on", "steering_wheel_heat_off")),
    "front_defrost": CapabilityDef("front_defrost", "Передний defrost", CapabilityStatus.EXPERIMENTAL, ("2222001",), ("front_defrost_on", "front_defrost_off")),
    "cabin_clean": CapabilityDef("cabin_clean", "Проветривание салона", CapabilityStatus.EXPERIMENTAL, ("2078020",), ("cabin_clean",)),
    "seat_heat_driver": CapabilityDef("seat_heat_driver", "Подогрев сиденья водителя", CapabilityStatus.DISCOVERED, ("2220001",), ()),
    "seat_heat_passenger": CapabilityDef("seat_heat_passenger", "Подогрев сиденья пассажира", CapabilityStatus.DISCOVERED, ("2220002",), ()),
    "front_windscreen_heat": CapabilityDef("front_windscreen_heat", "Электрообогрев лобового стекла", CapabilityStatus.DISCOVERED, ("2202111",), ()),
    "air_purifier": CapabilityDef("air_purifier", "Очиститель воздуха", CapabilityStatus.DISCOVERED, ("2078020",), ()),
    "sunroof": CapabilityDef("sunroof", "Люк", CapabilityStatus.EXPERIMENTAL, (), ("open_sunroof", "close_sunroof")),
    "sunshade": CapabilityDef("sunshade", "Шторка люка", CapabilityStatus.EXPERIMENTAL, (), ("open_sunshade", "close_sunshade")),
}


def capability_report(seen_codes: set[str] | list[str] | tuple[str, ...]) -> dict[str, dict[str, object]]:
    """Return capability metadata annotated with observed telemetry."""
    seen = {str(code) for code in seen_codes}
    return {
        key: {
            "name": item.name,
            "status": item.status.value,
            "signal_codes": list(item.signal_codes),
            "command_keys": list(item.command_keys),
            "telemetry_observed": any(code in seen for code in item.signal_codes) if item.signal_codes else False,
        }
        for key, item in CAPABILITIES.items()
    }
