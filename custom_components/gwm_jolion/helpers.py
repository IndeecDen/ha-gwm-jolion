"""Helpers for the GWM Jolion integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.exceptions import ConfigEntryAuthFailed

from .const import ITEM_MAP, KPA_TO_BAR, RAW_SENSOR_MAP, VEHICLE_STATUS_MAP, Conversion

_LOGGER = logging.getLogger(__name__)


def normalize_phone(raw: str) -> str:
    digits = "".join(ch for ch in str(raw) if ch.isdigit())
    if len(digits) == 11 and digits[0] in {"7", "8"}:
        digits = digits[1:]
    if len(digits) != 10:
        raise ConfigEntryAuthFailed("Phone must contain 10 Russian local digits")
    return digits


def value_to_number(value: Any) -> Any:
    try:
        text = str(value)
        if "." in text:
            return float(text)
        return int(text)
    except (TypeError, ValueError):
        return value


def _bool_from_raw(state: dict[str, Any], key: str, active_value: int = 1) -> bool | None:
    value = state.get(key)
    if value is None:
        return None
    return value == active_value


def _any_present_equals(state: dict[str, Any], keys: tuple[str, ...], value: int) -> bool | None:
    present = [state.get(key) for key in keys if state.get(key) is not None]
    if not present:
        return None
    return any(item == value for item in present)


def _seconds_to_minutes(value: Any) -> int | float | None:
    parsed = value_to_number(value)
    if not isinstance(parsed, (int, float)):
        return None
    minutes = parsed / 60
    return int(minutes) if minutes.is_integer() else round(minutes, 1)


def merge_vehicle_basics(state: dict[str, Any], basics: dict[str, Any]) -> None:
    if not isinstance(basics, dict) or not basics:
        return
    candidates = [basics]
    for key in ("vehicleBasicsInfo", "remoteControlInfo", "remoteControl", "data"):
        nested = basics.get(key)
        if isinstance(nested, dict):
            candidates.append(nested)
    merged: dict[str, Any] = {}
    for candidate in candidates:
        merged.update(candidate)
    mappings = {
        "airConditionerTemperature": ("climate_saved_temperature", value_to_number),
        "airConditionerStatusTime": ("climate_saved_runtime", _seconds_to_minutes),
        "airConditionerTime": ("climate_saved_runtime", _seconds_to_minutes),
        "engineStatusTime": ("engine_saved_runtime", _seconds_to_minutes),
        "seatHeatingControlTime": ("seat_heat_saved_runtime", _seconds_to_minutes),
        "seatHeatingType": ("seat_heating_type_raw", value_to_number),
        "frontDefrostStatus": ("front_defrost_status_basics_raw", value_to_number),
        "backDefrostStatus": ("rear_defrost_status_basics_raw", value_to_number),
        "airPurifierStatus": ("air_purifier_status_raw", value_to_number),
        "purifierTime": ("purifier_runtime", _seconds_to_minutes),
    }
    for cloud_key, (state_key, converter) in mappings.items():
        if cloud_key in merged and merged[cloud_key] is not None:
            state[state_key] = converter(merged[cloud_key])
    if state.get("driver_seat_heat_level_raw") is None and merged.get("leftFrontSeat") is not None:
        state["driver_seat_heat_level_raw"] = value_to_number(merged["leftFrontSeat"])
    if state.get("passenger_seat_heat_level_raw") is None and merged.get("rightFrontSeat") is not None:
        state["passenger_seat_heat_level_raw"] = value_to_number(merged["rightFrontSeat"])
    _LOGGER.debug("vehicleBasicsInfo keys: %s", sorted(merged.keys()))


def build_state(status: dict[str, Any], tbox: dict[str, Any], basics: dict[str, Any] | None = None) -> dict[str, Any]:
    state: dict[str, Any] = {
        "service_status": status.get("serviceStatus"),
        "oil_qty": status.get("oilQty"),
    }
    for item in status.get("items") or []:
        code = str(item.get("code"))
        raw = item.get("value")
        if code in ITEM_MAP:
            defn = ITEM_MAP[code]
            value = value_to_number(raw)
            if defn.convert == Conversion.PRESSURE_KPA_TO_BAR and isinstance(value, (int, float)):
                value = round(value / KPA_TO_BAR, 2)
            state[defn.key] = value
            continue
        if code in RAW_SENSOR_MAP:
            state[RAW_SENSOR_MAP[code].key] = value_to_number(raw)
            continue
        if code in VEHICLE_STATUS_MAP:
            state[VEHICLE_STATUS_MAP[code]] = value_to_number(raw)
            continue
        _LOGGER.debug("Unknown vehicle item code: %s = %s", code, raw)

    door_keys = ("door_front_left_raw", "door_rear_left_raw", "door_front_right_raw", "door_rear_right_raw")
    window_keys = ("window_2210001_raw", "window_2210002_raw", "window_2210003_raw", "window_2210004_raw")
    state["doors_open"] = _any_present_equals(state, door_keys, 1)
    state["door_front_left_open"] = _bool_from_raw(state, "door_front_left_raw")
    state["door_rear_left_open"] = _bool_from_raw(state, "door_rear_left_raw")
    state["door_front_right_open"] = _bool_from_raw(state, "door_front_right_raw")
    state["door_rear_right_open"] = _bool_from_raw(state, "door_rear_right_raw")
    state["windows_open"] = _any_present_equals(state, window_keys, 0)
    state["trunk_open"] = _bool_from_raw(state, "trunk_raw")
    state["vehicle_unlocked"] = _bool_from_raw(state, "central_lock_raw")
    engine_raw = state.get("engine_state_raw")
    state["engine_running"] = None if engine_raw is None else engine_raw == 2
    climate_raw = state.get("climate_raw")
    state["climate_on"] = None if climate_raw is None else climate_raw == 1
    state["gps_authorized"] = _bool_from_raw(state, "gps_authorized_raw")
    state["front_defrost_on"] = _bool_from_raw(state, "front_defrost_raw")
    state["rear_defrost_on"] = _bool_from_raw(state, "rear_defrost_raw")
    state["steering_wheel_heat_on"] = _bool_from_raw(state, "steering_wheel_heat_raw")
    state["front_windscreen_heat_on"] = _bool_from_raw(state, "front_windscreen_heat_raw")
    state["air_circulation_on"] = _bool_from_raw(state, "air_circulation_raw")
    tbox_status = tbox.get("status") if isinstance(tbox, dict) else None
    state["tbox_status"] = tbox_status
    state["tbox_online"] = str(tbox_status) == "1" if tbox_status is not None else None
    merge_vehicle_basics(state, basics or {})
    _LOGGER.debug("TBOX data keys: %s", list(tbox.keys()) if isinstance(tbox, dict) else "none")
    return state


def redact_vehicle(vehicle: dict[str, Any]) -> dict[str, Any]:
    hidden = {"vin", "showedVin", "engineNo", "simIccid", "imsi"}
    return {key: ("***REDACTED***" if key in hidden else value) for key, value in vehicle.items()}
