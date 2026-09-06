"""Persistent JSONL protocol-capture helpers for physical vehicle tests."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from .protocol import SIGNALS

CONF_PROTOCOL_CAPTURE = "protocol_capture_enabled"
DEFAULT_PROTOCOL_CAPTURE = False
CAPTURE_DIRECTORY = "gwm_jolion_protocol_capture"
CAPTURE_SCHEMA_VERSION = 1
MAX_DIAGNOSTICS_RECORDS = 2000
MAX_MARKER_LENGTH = 80


def new_capture_path(config_directory: str | Path, now: datetime | None = None) -> Path:
    """Return a unique path for one protocol-capture session."""
    timestamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%S_%fZ")
    return Path(config_directory) / f"gwm_code_search_{timestamp}.jsonl"


def _mapping_diff(
    previous: dict[str, Any],
    current: dict[str, Any],
    *,
    signal_metadata: bool = False,
) -> list[dict[str, Any]]:
    """Return deterministic previous -> current changes for two mappings."""
    changes: list[dict[str, Any]] = []
    for key in sorted(set(previous) | set(current)):
        had_previous = key in previous
        has_current = key in current
        previous_value = previous.get(key)
        current_value = current.get(key)
        if had_previous and has_current and previous_value == current_value:
            continue
        item: dict[str, Any] = {
            "key": key,
            "previous": previous_value if had_previous else None,
            "value": current_value if has_current else None,
            "initial": not had_previous,
            "removed": not has_current,
        }
        if signal_metadata:
            info = SIGNALS.get(key)
            item["code"] = key
            item.pop("key", None)
            if info is not None:
                item["known_as"] = info.key
                item["description"] = info.description
                item["status"] = info.status.value
            else:
                item["known_as"] = "unknown_signal"
                item["description"] = "Неизвестный сигнал GWM"
                item["status"] = "unknown"
        changes.append(item)
    return changes


def build_capture_record(
    *,
    sequence: int,
    timestamp: datetime,
    source: str,
    integration_version: str,
    signals: dict[str, Any],
    previous_signals: dict[str, Any],
    unknown_signals: dict[str, Any],
    vehicle_basics: dict[str, Any],
    previous_vehicle_basics: dict[str, Any],
    baseline: bool,
) -> dict[str, Any]:
    """Build one self-contained, privacy-limited JSONL refresh record."""
    normalized_signals = {str(key): value for key, value in signals.items()}
    normalized_unknown = {str(key): value for key, value in unknown_signals.items()}
    normalized_basics = {str(key): value for key, value in vehicle_basics.items()}
    signal_changes = _mapping_diff(previous_signals, normalized_signals, signal_metadata=True)
    basics_changes = _mapping_diff(previous_vehicle_basics, normalized_basics)
    return {
        "schema": CAPTURE_SCHEMA_VERSION,
        "type": "refresh",
        "integration_version": integration_version,
        "seq": sequence,
        "time": timestamp.isoformat(),
        "source": source,
        "baseline": baseline,
        "signals": normalized_signals,
        "changes": [] if baseline else signal_changes,
        "changes_count": 0 if baseline else len(signal_changes),
        "unknown_signals": normalized_unknown,
        "vehicle_basics": normalized_basics,
        "vehicle_basics_changes": [] if baseline else basics_changes,
        "vehicle_basics_changes_count": 0 if baseline else len(basics_changes),
        "privacy": {
            "contains_vin": False,
            "contains_credentials": False,
            "contains_account": False,
            "contains_exact_location": False,
            "contains_device_identifiers": False,
        },
    }


def normalize_marker(label: object) -> str:
    """Normalize a short human test marker for one-line JSONL storage."""
    marker = " ".join(str(label or "").split())
    if not marker:
        raise ValueError("Marker cannot be empty")
    if len(marker) > MAX_MARKER_LENGTH:
        raise ValueError(f"Marker cannot exceed {MAX_MARKER_LENGTH} characters")
    return marker


def build_marker_record(
    *,
    sequence: int,
    timestamp: datetime,
    integration_version: str,
    label: str,
) -> dict[str, Any]:
    """Build a user-supplied marker record without touching signal baselines."""
    return {
        "schema": CAPTURE_SCHEMA_VERSION,
        "type": "marker",
        "integration_version": integration_version,
        "seq": sequence,
        "time": timestamp.isoformat(),
        "label": normalize_marker(label),
        "privacy": {
            "automatic_vehicle_identifiers_included": False,
            "label_is_user_supplied": True,
        },
    }


def append_jsonl(path: str | Path, record: dict[str, Any]) -> None:
    """Append exactly one record to a JSONL file."""
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":"), default=str))
        handle.write("\n")


def read_jsonl_for_diagnostics(
    path: str | Path,
    max_records: int = MAX_DIAGNOSTICS_RECORDS,
) -> dict[str, Any]:
    """Read a bounded capture session for inclusion in HA diagnostics."""
    file_path = Path(path)
    if not file_path.exists():
        return {
            "records": [],
            "records_in_file": 0,
            "records_exported": 0,
            "truncated": False,
            "invalid_lines": 0,
            "read_error": "file_not_found",
        }

    records: list[dict[str, Any]] = []
    records_in_file = 0
    invalid_lines = 0
    try:
        with file_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                records_in_file += 1
                if len(records) >= max_records:
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    invalid_lines += 1
                    continue
                if isinstance(item, dict):
                    records.append(item)
                else:
                    invalid_lines += 1
    except OSError as err:
        return {
            "records": records,
            "records_in_file": records_in_file,
            "records_exported": len(records),
            "truncated": records_in_file > len(records),
            "invalid_lines": invalid_lines,
            "read_error": str(err),
        }

    return {
        "records": records,
        "records_in_file": records_in_file,
        "records_exported": len(records),
        "truncated": records_in_file > len(records),
        "invalid_lines": invalid_lines,
        "read_error": None,
    }
