"""Pure helpers for safe GWM remote-command handling."""

from __future__ import annotations

from typing import Any

AUTH_ERROR_CODES = frozenset({"401", "401000", "308001", "308002", "308003"})

# Observed/known T5 result states.  A terminal error must not keep the
# serialized command queue occupied for the full polling timeout.
T5_SUCCESS_CODES = frozenset({"0", "6", "10"})
T5_PENDING_CODES = frozenset({"1000", "2000"})
T5_NON_FINAL_CODES = frozenset({"11"})


def is_auth_error_code(code: object) -> bool:
    """Return True when a GWM response code means authorization must be renewed."""
    return str(code) in AUTH_ERROR_CODES


def classify_t5_result_code(code: object) -> str:
    """Classify one T5 result code as success, pending, unknown or error.

    Code 11 has been observed as a non-final intermediate state, so it remains
    pollable. Empty result codes are also treated conservatively as unknown.
    Any other explicit code is terminal and should be surfaced immediately.
    """
    normalized = "" if code is None else str(code).strip()
    if normalized in T5_SUCCESS_CODES:
        return "success"
    if normalized in T5_PENDING_CODES or normalized in T5_NON_FINAL_CODES:
        return "pending"
    if not normalized:
        return "unknown"
    return "error"


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
