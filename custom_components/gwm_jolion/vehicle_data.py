"""Dependency-free helpers for normalized GWM vehicle metadata."""

from __future__ import annotations

from typing import Any


def _as_number(value: Any) -> int | float | None:
    """Convert a cloud value to a number when possible."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return int(number) if number.is_integer() else number


def normalize_vehicle_metadata(vehicle: dict[str, Any]) -> dict[str, Any]:
    """Return stable, user-friendly metadata from acquireVehicles data."""
    brand_raw = str(vehicle.get("brandName") or vehicle.get("otBrandName") or "HAVAL").strip()
    vehicle_type_raw = str(vehicle.get("vtype") or vehicle.get("canSignalType") or "").strip()
    model_raw = str(vehicle.get("modelName") or vehicle.get("modelCode") or "").strip()

    upper_type = vehicle_type_raw.upper()
    upper_model = model_raw.upper()
    if upper_type == "JOLION" or "JOLION" in upper_model or "HAVALA01" in upper_model:
        display_model = "Haval Jolion"
    elif model_raw:
        display_model = model_raw
    elif vehicle_type_raw:
        display_model = vehicle_type_raw.title()
    else:
        display_model = "Haval"

    brand = "HAVAL" if "HAVAL" in brand_raw.upper() else brand_raw

    return {
        "brand": brand,
        "model": display_model,
        "vehicle_type": vehicle_type_raw or None,
        "engine_type": vehicle.get("engineType") or None,
        "tank_capacity_l": _as_number(vehicle.get("tankCapacity")),
        "vehicle_config": vehicle.get("config") or None,
        "telematics_platform": vehicle.get("belongPlatform") or None,
        "model_code_raw": vehicle.get("modelCode") or None,
        "color": vehicle.get("color") or None,
    }


def calculate_fuel_percent(fuel_liters: Any, tank_capacity_l: Any) -> int | None:
    """Calculate fuel percentage from cloud litres and declared tank capacity."""
    fuel = _as_number(fuel_liters)
    capacity = _as_number(tank_capacity_l)
    if fuel is None or capacity is None or capacity <= 0:
        return None
    percent = round(float(fuel) / float(capacity) * 100)
    return max(0, min(100, percent))


def describe_structure(value: Any, *, depth: int = 0, max_depth: int = 4) -> dict[str, Any]:
    """Describe response shape without exposing response values."""
    if depth >= max_depth:
        return {"type": type(value).__name__, "truncated": True}

    if isinstance(value, dict):
        keys = sorted(str(key) for key in value.keys())
        children: dict[str, Any] = {}
        for key in keys[:50]:
            children[key] = describe_structure(value.get(key), depth=depth + 1, max_depth=max_depth)
        result: dict[str, Any] = {
            "type": "dict",
            "keys": keys[:50],
            "children": children,
        }
        if len(keys) > 50:
            result["truncated_keys"] = len(keys) - 50
        return result

    if isinstance(value, list):
        item_types = sorted({type(item).__name__ for item in value})
        result = {"type": "list", "length": len(value), "item_types": item_types}
        if value:
            result["first_item"] = describe_structure(value[0], depth=depth + 1, max_depth=max_depth)
        return result

    return {"type": type(value).__name__}
