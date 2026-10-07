"""Small, coordinate-free health snapshot shared by entities and diagnostics."""
from __future__ import annotations

from datetime import datetime, timezone
import math
import time


def timestamp(value):
    """Return a finite epoch timestamp; unknown timestamps stay unknown."""
    if isinstance(value, datetime):
        value = value.timestamp()
    if isinstance(value, bool):
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) and value > 0 else None


def iso_time(value):
    value = timestamp(value)
    return datetime.fromtimestamp(value, timezone.utc).isoformat() if value else None


def snapshot(coordinator, now=None):
    now = time.time() if now is None else now
    history = getattr(coordinator, "trip_history", None)
    enabled = bool(getattr(history, "enabled", False))
    location = history.location() if enabled else (coordinator.data or {}).get("location", {})
    location = location or {}
    stamp_ms = timestamp(location.get("gps_timestamp_ms"))
    observed = stamp_ms / 1000 if stamp_ms else None
    known = bool(location.get("time_known", False))
    fix_age = max(0, int(now - observed)) if known and observed else None
    received_ms = timestamp(getattr(history, "last_received_ms", None))
    cloud_update = timestamp(getattr(coordinator, "last_successful_update", None))
    configured = bool((coordinator.data or {}).get("vin"))
    return {
        "cloud_status": ("online" if getattr(coordinator, "last_update_success", False)
                         else "offline") if configured or cloud_update else "unknown",
        "cloud_last_update": iso_time(cloud_update),
        "cloud_data_age_seconds": max(0, int(now - cloud_update)) if cloud_update else None,
        "location_source": location.get("source", "cloud") if location else "unknown",
        "location_timestamp": iso_time(observed) if known else None,
        "location_observed_at": iso_time(observed),
        "location_age_seconds": fix_age,
        "location_time_known": known,
        # Cloud time is an observation time, not a measured GNSS fix time.
        "location_freshness": "unknown" if fix_age is None else "stale" if fix_age > 120 else "fresh",
        "locator_enabled": enabled,
        "locator_last_received": iso_time(received_ms / 1000) if received_ms else None,
        "locator_receive_age_seconds": max(0, int(now - received_ms / 1000)) if received_ms else None,
        "locator_transport": ("yandex_disk" if getattr(history, "relay", None) else "https") if enabled else None,
        "locator_relay_status": getattr(getattr(history, "relay", None), "status", None),
    }
