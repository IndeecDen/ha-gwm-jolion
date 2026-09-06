"""Pure helpers for safe GWM remote-command handling."""

from __future__ import annotations

from typing import Any

AUTH_ERROR_CODES = frozenset({"401", "401000", "308001", "308002", "308003"})


def is_auth_error_code(code: object) -> bool:
    """Return True when a GWM response code means authorization must be renewed."""
    return str(code) in AUTH_ERROR_CODES


def remote_start_block_reason(state: dict[str, Any] | None) -> str | None:
    """Return a conservative reason to block remote engine start.

    Only already-confirmed Jolion telemetry is used here. Missing/unknown values do
    not block a command because the coordinator refreshes telemetry immediately
    before evaluating these conditions.
    """
    if not isinstance(state, dict):
        return None

    if state.get("engine_running") is True:
        return "двигатель уже работает"
    if state.get("vehicle_unlocked") is True:
        return "автомобиль не закрыт"
    if state.get("doors_open") is True:
        return "открыта одна или несколько дверей"
    if state.get("trunk_open") is True:
        return "открыт багажник"
    return None
