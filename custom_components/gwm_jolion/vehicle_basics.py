"""Safe parsing helpers for GWM vehicleBasicsInfo responses."""

from __future__ import annotations

from typing import Any

# Only non-sensitive fields that are useful for protocol analysis and support.
# User/account identifiers and the VIN are deliberately excluded.
VEHICLE_BASICS_SAFE_KEYS = frozenset(
    {
        "airConditionerTemperature",
        "airConditionerStatusTime",
        "airConditionerTime",
        "airPurifierStatus",
        "airPurifierTime",
        "purifierTime",
        "backDefrostStatus",
        "blowingMode",
        "cabinCleanNum",
        "cabinCleanTime",
        "engineStatusTime",
        "frontDefrostStatus",
        "frontDefrostTime",
        "frontWindshieldFullScreenHeatingTime",
        "hybridEngineRunningTime",
        "leftBackSeat",
        "leftBackWindow",
        "leftFrontSeat",
        "leftFrontWindow",
        "leftThirdRowSeat",
        "powerGear",
        "rearDefrostTime",
        "rightBackSeat",
        "rightBackWindow",
        "rightFrontSeat",
        "rightFrontWindow",
        "rightThirdRowSeat",
        "seatHeatingControlTime",
        "seatHeatingType",
        "shadeScreen",
        "skyLight",
        "steeringWheelHeatingTime",
    }
)

# GWM has returned vehicleBasicsInfo in several wrapper layouts.  The Russian
# Jolion response observed in alpha.10 is data -> config.
_WRAPPER_KEYS = (
    "vehicleBasicsInfo",
    "remoteControlInfo",
    "remoteControl",
    "data",
    "config",
)


def flatten_vehicle_basics(basics: dict[str, Any]) -> dict[str, Any]:
    """Flatten known vehicleBasicsInfo wrapper dictionaries."""
    if not isinstance(basics, dict) or not basics:
        return {}

    merged: dict[str, Any] = {}
    queue: list[dict[str, Any]] = [basics]
    visited: set[int] = set()

    while queue:
        candidate = queue.pop(0)
        candidate_id = id(candidate)
        if candidate_id in visited:
            continue
        visited.add(candidate_id)
        merged.update(candidate)

        for key in _WRAPPER_KEYS:
            nested = candidate.get(key)
            if isinstance(nested, dict):
                queue.append(nested)

    return merged


def vehicle_basics_snapshot(basics: dict[str, Any]) -> dict[str, Any]:
    """Return a non-sensitive value snapshot for diagnostics."""
    merged = flatten_vehicle_basics(basics)
    return {
        key: merged[key]
        for key in sorted(VEHICLE_BASICS_SAFE_KEYS)
        if key in merged and merged[key] is not None
    }
