"""Diagnostics support for GWM Jolion."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from .const import DOMAIN, VERSION
from .coordinator import GwmJolionCoordinator
from .protocol import signal_report
from .protocol_capture import read_jsonl_for_diagnostics

_REDACTED = "**REDACTED**"
_SENSITIVE_NORMALIZED_KEYS = {
    "accesstoken", "account", "deviceid", "engineno", "iccid", "imsi",
    "latitude", "longitude", "password", "phone", "securitypassword",
    "securitypin", "shareid", "showedvin", "token", "vehicleid",
    "vehiclenumber", "vin",
}


def _normalize_key(key: object) -> str:
    return "".join(ch for ch in str(key).lower() if ch.isalnum())


def _redact(value: Any) -> Any:
    """Recursively redact credentials, identifiers and exact coordinates."""
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            normalized = _normalize_key(key_text)
            if normalized in _SENSITIVE_NORMALIZED_KEYS:
                redacted[key_text] = _REDACTED
            else:
                redacted[key_text] = _redact(item)
        return redacted
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, tuple):
        return [_redact(item) for item in value]
    return value


def _base_diagnostics_payload(
    entry: ConfigEntry,
    coordinator: GwmJolionCoordinator,
) -> dict[str, Any]:
    data = coordinator.data or {}
    state = data.get("state") or {}
    public_state = {key: value for key, value in state.items() if not str(key).startswith("_")}
    last_update = coordinator.last_successful_update
    last_command = coordinator.last_command_at
    capture_name = Path(coordinator.protocol_capture_path).name if coordinator.protocol_capture_path else None
    capture_time = coordinator.protocol_capture_last_record_time

    return {
        "integration": {"domain": DOMAIN, "version": VERSION, "entry_title": entry.title},
        "config": _redact({"data": dict(entry.data), "options": dict(entry.options)}),
        "vehicle": _redact(data.get("vehicle") or {}),
        "state": _redact(public_state),
        "vehicle_basics": _redact(data.get("vehicle_basics") or {}),
        "vehicle_basics_diagnostics": _redact(data.get("vehicle_basics_diagnostics") or {}),
        "coordinator": {
            "last_successful_update": last_update.isoformat() if last_update else None,
            "seen_signal_codes": sorted(coordinator.seen_signal_codes),
            "unknown_signal_history": _redact(coordinator.unknown_signal_history),
            "signal_change_history": _redact(coordinator.signal_change_history),
            "capabilities": coordinator.capability_report,
        },
        "protocol_capture": {
            "enabled": coordinator.protocol_capture_enabled,
            "file_name": capture_name,
            "records_written": coordinator.protocol_capture_sequence,
            "last_record_time": capture_time.isoformat() if capture_time else None,
            "last_source": coordinator.protocol_capture_last_source,
            "last_changes_count": coordinator.protocol_capture_last_changes_count,
            "last_marker": coordinator.protocol_capture_last_marker,
            "last_error": coordinator.protocol_capture_last_error,
            "session_export": None,
        },
        "protocol": signal_report(coordinator.seen_signal_codes),
        "last_remote_command": {
            "name": coordinator.last_command_name,
            "result_code": coordinator.last_command_result_code,
            "result_message": coordinator.last_command_result_message,
            "time": last_command.isoformat() if last_command else None,
            "in_progress": coordinator.command_in_progress,
        },
        "privacy": {
            "location_included": False,
            "vin_included": False,
            "vehicle_number_included": False,
            "credentials_included": False,
            "capture_automatic_identifiers_included": False,
            "capture_markers_are_user_supplied": True,
        },
    }


async def _async_diagnostics_payload(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinator: GwmJolionCoordinator,
) -> dict[str, Any]:
    payload = _base_diagnostics_payload(entry, coordinator)
    if coordinator.protocol_capture_path:
        capture_export = await hass.async_add_executor_job(
            read_jsonl_for_diagnostics,
            coordinator.protocol_capture_path,
        )
        payload["protocol_capture"]["session_export"] = _redact(capture_export)
    return payload


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return redacted diagnostics including the current capture session."""
    coordinator: GwmJolionCoordinator = hass.data[DOMAIN][entry.entry_id]
    return await _async_diagnostics_payload(hass, entry, coordinator)


async def async_get_device_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
    device: DeviceEntry,
) -> dict[str, Any]:
    """Return the same safe diagnostics from the vehicle device page."""
    coordinator: GwmJolionCoordinator = hass.data[DOMAIN][entry.entry_id]
    payload = await _async_diagnostics_payload(hass, entry, coordinator)
    payload["device"] = {
        "name": device.name,
        "model": device.model,
        "manufacturer": device.manufacturer,
    }
    return payload
