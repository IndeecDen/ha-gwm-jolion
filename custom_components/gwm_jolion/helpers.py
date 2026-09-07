"""Helpers for the GWM Jolion integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.exceptions import ConfigEntryAuthFailed

from .const import ITEM_MAP, KPA_TO_BAR, RAW_SENSOR_MAP, VEHICLE_STATUS_MAP, Conversion
from .vehicle_basics import flatten_vehicle_basics, vehicle_basics_snapshot
from .vehicle_data import describe_structure

_LOGGER = logging.getLogger(__name__)

_STATUS_SAFE_META_KEYS = (
    "acquisitionTime", "uploadTime", "updateTime", "oilQty", "percentageOfOil", "charge",
    "serviceStatus", "deviceType", "command",
)

_TBOX_SAFE_META_KEYS = (
    "status", "signal", "signalLevel", "networkType", "network",
    "acquisitionTime", "uploadTime", "updateTime",
)


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


def _window_open_from_raw(state: dict[str, Any], key: str) -> bool | None:
    """Decode only window states proven by field capture.

    Raw 1 is closed. Raw 2 and 3 are non-closed states. Physical positions of
    2210001..2210004 are field-confirmed; exact 2-vs-3 intermediate semantics
    were isolated for 2210001 only, so the generic binary sensor stays conservative.
    """
    value = state.get(key)
    if value is None:
        return None
    if value == 1:
        return False
    if value in {2, 3}:
        return True
    return None


def _any_window_open(state: dict[str, Any], keys: tuple[str, ...]) -> bool | None:
    values = [_window_open_from_raw(state, key) for key in keys if state.get(key) is not None]
    if not values:
        return None
    if any(value is True for value in values):
        return True
    if all(value is False for value in values):
        return False
    return None


def _seconds_to_minutes(value: Any) -> int | float | None:
    parsed = value_to_number(value)
    if not isinstance(parsed, (int, float)):
        return None
    minutes = parsed / 60
    return int(minutes) if minutes.is_integer() else round(minutes, 1)


def _safe_scalar_snapshot(source: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    """Return explicitly allowed scalar values, including present null values."""
    if not isinstance(source, dict):
        return {}
    result: dict[str, Any] = {}
    for key in keys:
        if key not in source:
            continue
        value = source.get(key)
        if value is None or isinstance(value, (str, int, float, bool)):
            result[key] = value
    return result


def merge_vehicle_basics(state: dict[str, Any], basics: dict[str, Any]) -> None:
    """Merge conservative vehicleBasicsInfo fields into coordinator state."""
    merged = flatten_vehicle_basics(basics)
    state["_vehicle_basics_seen_keys"] = sorted(str(key) for key in merged)
    state["_vehicle_basics_structure"] = describe_structure(basics)
    if not merged:
        return

    mappings = {
        "airConditionerTemperature": ("climate_saved_temperature", value_to_number),
        "airConditionerStatusTime": ("climate_saved_runtime", _seconds_to_minutes),
        "airConditionerTime": ("climate_saved_runtime", _seconds_to_minutes),
        "engineStatusTime": ("engine_saved_runtime", _seconds_to_minutes),
        "seatHeatingControlTime": ("seat_heat_saved_runtime", _seconds_to_minutes),
        "seatHeatingType": ("seat_heating_type_raw", value_to_number),
        "frontDefrostStatus": ("front_defrost_status_basics_raw", value_to_number),
        "frontDefrostTime": ("front_defrost_saved_runtime", _seconds_to_minutes),
        "backDefrostStatus": ("rear_defrost_status_basics_raw", value_to_number),
        "rearDefrostTime": ("rear_defrost_saved_runtime", _seconds_to_minutes),
        "frontWindshieldFullScreenHeatingTime": ("front_windscreen_heat_saved_runtime", _seconds_to_minutes),
        "steeringWheelHeatingTime": ("steering_wheel_heat_saved_runtime", _seconds_to_minutes),
        "airPurifierStatus": ("air_purifier_status_raw", value_to_number),
        "airPurifierTime": ("purifier_runtime", _seconds_to_minutes),
        "purifierTime": ("purifier_runtime", _seconds_to_minutes),
        "skyLight": ("sunroof_basics_raw", value_to_number),
        "shadeScreen": ("sunshade_basics_raw", value_to_number),
    }
    for cloud_key, (state_key, converter) in mappings.items():
        if cloud_key in merged and merged[cloud_key] is not None:
            state[state_key] = converter(merged[cloud_key])

    # leftFrontSeat/rightFrontSeat from vehicleBasicsInfo are saved remote-control
    # presets, not live heater states. Live 2220001/2220002 telemetry is the only
    # source for the live seat heat level; absent live telemetry stays unavailable.
    _LOGGER.debug("vehicleBasicsInfo keys: %s", sorted(merged.keys()))


def build_state(status: dict[str, Any], tbox: dict[str, Any], basics: dict[str, Any] | None = None) -> dict[str, Any]:
    state: dict[str, Any] = {
        "service_status": status.get("serviceStatus"),
        "oil_qty": status.get("oilQty"),
    }
    seen_signals: dict[str, Any] = {}
    unknown_signals: dict[str, Any] = {}
    signal_units: dict[str, str] = {}
    signal_item_seen_keys: set[str] = set()

    for item in status.get("items") or []:
        if not isinstance(item, dict):
            continue
        signal_item_seen_keys.update(str(key) for key in item)
        code = str(item.get("code"))
        raw = item.get("value")
        value = value_to_number(raw)
        seen_signals[code] = value
        unit = item.get("unit")
        if unit not in (None, ""):
            signal_units[code] = str(unit)

        if code in ITEM_MAP:
            defn = ITEM_MAP[code]
            if defn.convert == Conversion.PRESSURE_KPA_TO_BAR and isinstance(value, (int, float)):
                value = round(value / KPA_TO_BAR, 2)
            state[defn.key] = value
            continue
        if code in RAW_SENSOR_MAP:
            state[RAW_SENSOR_MAP[code].key] = value
            continue
        if code in VEHICLE_STATUS_MAP:
            state[VEHICLE_STATUS_MAP[code]] = value
            continue

        unknown_signals[code] = value
        _LOGGER.debug("Unknown vehicle item code: %s = %s", code, raw)

    door_keys = ("door_front_left_raw", "door_rear_left_raw", "door_front_right_raw", "door_rear_right_raw")
    window_keys = ("window_2210001_raw", "window_2210002_raw", "window_2210003_raw", "window_2210004_raw")
    state["doors_open"] = _any_present_equals(state, door_keys, 1)
    state["door_front_left_open"] = _bool_from_raw(state, "door_front_left_raw")
    state["door_rear_left_open"] = _bool_from_raw(state, "door_rear_left_raw")
    state["door_front_right_open"] = _bool_from_raw(state, "door_front_right_raw")
    state["door_rear_right_open"] = _bool_from_raw(state, "door_rear_right_raw")
    state["windows_open"] = _any_window_open(state, window_keys)
    state["window_2210001_open"] = _window_open_from_raw(state, "window_2210001_raw")
    state["window_2210002_open"] = _window_open_from_raw(state, "window_2210002_raw")
    state["window_2210003_open"] = _window_open_from_raw(state, "window_2210003_raw")
    state["window_2210004_open"] = _window_open_from_raw(state, "window_2210004_raw")
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

    state["_seen_signals"] = seen_signals
    state["_unknown_signals"] = unknown_signals
    state["_signal_units"] = signal_units
    state["_signal_item_seen_keys"] = sorted(signal_item_seen_keys)
    state["_status_meta"] = _safe_scalar_snapshot(status, _STATUS_SAFE_META_KEYS)
    state["_status_structure"] = describe_structure(status)
    state["_tbox_meta"] = _safe_scalar_snapshot(tbox, _TBOX_SAFE_META_KEYS)
    state["_tbox_structure"] = describe_structure(tbox)

    merge_vehicle_basics(state, basics or {})
    _LOGGER.debug("TBOX data keys: %s", list(tbox.keys()) if isinstance(tbox, dict) else "none")
    return state


def redact_vehicle(vehicle: dict[str, Any]) -> dict[str, Any]:
    hidden = {"vin", "showedVin", "engineNo", "simIccid", "imsi", "vehicleId", "vehicleNumber", "shareId"}
    return {key: ("***REDACTED***" if key in hidden else value) for key, value in vehicle.items()}
