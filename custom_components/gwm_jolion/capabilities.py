"""Capability metadata and manual equipment settings for GWM Jolion."""

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
    "windows_close": CapabilityDef("windows_close", "Окна", CapabilityStatus.IMPLEMENTED, ("2210001", "2210002", "2210003", "2210004"), ("close_windows", "open_windows")),
    "climate": CapabilityDef("climate", "Климат", CapabilityStatus.CONFIRMED, ("2202001",), ()),
    "rear_defrost": CapabilityDef("rear_defrost", "Обогрев заднего стекла", CapabilityStatus.IMPLEMENTED, ("2210032",), ("rear_defrost_on", "rear_defrost_off")),
    "steering_wheel_heat": CapabilityDef("steering_wheel_heat", "Обогрев руля", CapabilityStatus.IMPLEMENTED, ("2060016",), ("steering_wheel_heat_on", "steering_wheel_heat_off")),
    "front_defrost": CapabilityDef("front_defrost", "Передний defrost", CapabilityStatus.EXPERIMENTAL, ("2222001",), ("front_defrost_on", "front_defrost_off")),
    "cabin_clean": CapabilityDef("cabin_clean", "Проветривание салона", CapabilityStatus.EXPERIMENTAL, ("2078020",), ("cabin_clean",)),
    "seat_heat_driver": CapabilityDef("seat_heat_driver", "Подогрев сиденья водителя", CapabilityStatus.CONFIRMED, ("2220001",), ()),
    "seat_heat_passenger": CapabilityDef("seat_heat_passenger", "Подогрев сиденья пассажира", CapabilityStatus.CONFIRMED, ("2220002",), ()),
    "front_windscreen_heat": CapabilityDef("front_windscreen_heat", "Электрообогрев лобового стекла", CapabilityStatus.DISCOVERED, ("2202111",), ()),
    "air_purifier": CapabilityDef("air_purifier", "Очиститель воздуха", CapabilityStatus.DISCOVERED, ("2078020",), ()),
    "sunroof": CapabilityDef("sunroof", "Панорамная крыша / люк", CapabilityStatus.EXPERIMENTAL, (), ("open_sunroof", "close_sunroof")),
    "sunshade": CapabilityDef("sunshade", "Шторка панорамной крыши", CapabilityStatus.EXPERIMENTAL, (), ("open_sunshade", "close_sunshade")),
}


_ALL_MANUAL_CAPABILITY_OPTIONS: dict[str, str] = {
    "sunroof": "feature_sunroof",
    "sunshade": "feature_sunshade",
    "steering_wheel_heat": "feature_steering_wheel_heat",
    "rear_defrost": "feature_rear_defrost",
    "front_defrost": "feature_front_defrost",
    "front_windscreen_heat": "feature_front_windscreen_heat",
    "seat_heat_driver": "feature_driver_seat_heat",
    "seat_heat_passenger": "feature_passenger_seat_heat",
    "cabin_clean": "feature_cabin_clean",
    "air_purifier": "feature_air_purifier",
}

_PUBLIC_MANUAL_CAPABILITIES = frozenset(
    {
        "steering_wheel_heat",
        "rear_defrost",
        "seat_heat_driver",
        "seat_heat_passenger",
    }
)

# alpha.20 only asks the user about equipment that currently affects a useful
# public status or command. Discovery-only/experimental features remain in the
# protocol model but are no longer shown in the normal Options Flow.
MANUAL_CAPABILITY_OPTIONS: dict[str, str] = {
    key: value
    for key, value in _ALL_MANUAL_CAPABILITY_OPTIONS.items()
    if key in _PUBLIC_MANUAL_CAPABILITIES
}

DEFAULT_MANUAL_CAPABILITIES: dict[str, bool] = {
    key: True for key in MANUAL_CAPABILITY_OPTIONS
}

STATE_KEY_CAPABILITY: dict[str, str] = {
    "steering_wheel_heat_on": "steering_wheel_heat",
    "steering_wheel_heat_raw": "steering_wheel_heat",
    "steering_wheel_heat_saved_runtime": "steering_wheel_heat",
    "rear_defrost_on": "rear_defrost",
    "rear_defrost_raw": "rear_defrost",
    "rear_defrost_status_basics_raw": "rear_defrost",
    "rear_defrost_saved_runtime": "rear_defrost",
    "front_defrost_on": "front_defrost",
    "front_defrost_raw": "front_defrost",
    "front_defrost_status_basics_raw": "front_defrost",
    "front_defrost_saved_runtime": "front_defrost",
    "front_windscreen_heat_on": "front_windscreen_heat",
    "front_windscreen_heat_raw": "front_windscreen_heat",
    "front_windscreen_heat_saved_runtime": "front_windscreen_heat",
    "driver_seat_heat_level_raw": "seat_heat_driver",
    "passenger_seat_heat_level_raw": "seat_heat_passenger",
    "air_circulation_on": "cabin_clean",
    "air_circulation_raw": "cabin_clean",
    "air_purifier_status_raw": "air_purifier",
    "purifier_runtime": "air_purifier",
    "sunroof_basics_raw": "sunroof",
    "sunshade_basics_raw": "sunshade",
}


def resolve_manual_capabilities(options: dict[str, object] | None) -> dict[str, bool]:
    """Resolve only public equipment flags from config-entry options."""
    source = options or {}
    return {
        capability: bool(source.get(option_key, DEFAULT_MANUAL_CAPABILITIES[capability]))
        for capability, option_key in MANUAL_CAPABILITY_OPTIONS.items()
    }


def capability_for_command(command_key: str) -> str | None:
    """Return the capability that owns a remote command, if any."""
    for key, item in CAPABILITIES.items():
        if command_key in item.command_keys:
            return key
    return None


def capability_for_state_key(state_key: str) -> str | None:
    """Return optional equipment capability associated with a state key."""
    return STATE_KEY_CAPABILITY.get(state_key)


def capability_report(
    seen_codes: set[str] | list[str] | tuple[str, ...],
    enabled: dict[str, bool] | None = None,
) -> dict[str, dict[str, object]]:
    """Return capability metadata annotated with telemetry and manual settings."""
    seen = {str(code) for code in seen_codes}
    enabled_map = enabled or {}
    return {
        key: {
            "name": item.name,
            "status": item.status.value,
            "signal_codes": list(item.signal_codes),
            "command_keys": list(item.command_keys),
            "telemetry_observed": any(code in seen for code in item.signal_codes) if item.signal_codes else False,
            "enabled": enabled_map.get(key, True),
            "manual_option": MANUAL_CAPABILITY_OPTIONS.get(key),
        }
        for key, item in CAPABILITIES.items()
    }
