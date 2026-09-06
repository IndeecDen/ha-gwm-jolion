from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import sys
import types

import pytest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT / "custom_components" / "gwm_jolion"


def load_capture_module():
    custom_components = types.ModuleType("custom_components")
    custom_components.__path__ = [str(ROOT / "custom_components")]
    sys.modules.setdefault("custom_components", custom_components)

    package = types.ModuleType("custom_components.gwm_jolion")
    package.__path__ = [str(PACKAGE_ROOT)]
    sys.modules.setdefault("custom_components.gwm_jolion", package)

    for module_name in ("protocol", "protocol_capture"):
        full_name = f"custom_components.gwm_jolion.{module_name}"
        path = PACKAGE_ROOT / f"{module_name}.py"
        spec = importlib.util.spec_from_file_location(full_name, path)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules[full_name] = module
        spec.loader.exec_module(module)

    return sys.modules["custom_components.gwm_jolion.protocol_capture"]


def test_capture_baseline_contains_full_snapshots_without_changes(tmp_path):
    capture = load_capture_module()
    record = capture.build_capture_record(
        sequence=1,
        timestamp=datetime(2026, 9, 6, 16, 0, tzinfo=timezone.utc),
        source="poll",
        integration_version="test",
        signals={"2220001": 0, "9999999": 7},
        previous_signals={},
        unknown_signals={"9999999": 7},
        vehicle_basics={"leftFrontSeat": 0},
        previous_vehicle_basics={},
        baseline=True,
    )

    assert record["type"] == "refresh"
    assert record["baseline"] is True
    assert record["signals"]["2220001"] == 0
    assert record["unknown_signals"] == {"9999999": 7}
    assert record["changes"] == []
    assert record["vehicle_basics_changes"] == []
    assert record["privacy"]["contains_vin"] is False


def test_capture_diff_has_known_and_unknown_signal_metadata():
    capture = load_capture_module()
    record = capture.build_capture_record(
        sequence=2,
        timestamp=datetime(2026, 9, 6, 16, 1, tzinfo=timezone.utc),
        source="manual_button",
        integration_version="test",
        signals={"2220001": 3, "9999999": 8},
        previous_signals={"2220001": 0, "9999999": 7},
        unknown_signals={"9999999": 8},
        vehicle_basics={"leftFrontSeat": 3},
        previous_vehicle_basics={"leftFrontSeat": 0},
        baseline=False,
    )

    assert record["source"] == "manual_button"
    assert record["changes_count"] == 2
    changes = {item["code"]: item for item in record["changes"]}
    assert changes["2220001"]["previous"] == 0
    assert changes["2220001"]["value"] == 3
    assert changes["2220001"]["known_as"] == "driver_seat_heat_level_raw"
    assert changes["9999999"]["known_as"] == "unknown_signal"
    assert record["vehicle_basics_changes"] == [
        {
            "key": "leftFrontSeat",
            "previous": 0,
            "value": 3,
            "initial": False,
            "removed": False,
        }
    ]


def test_marker_is_separate_short_record():
    capture = load_capture_module()
    marker = capture.build_marker_record(
        sequence=3,
        timestamp=datetime(2026, 9, 6, 16, 2, tzinfo=timezone.utc),
        integration_version="test",
        label="  DRIVER_SEAT_L3   ",
    )

    assert marker["type"] == "marker"
    assert marker["label"] == "DRIVER_SEAT_L3"
    assert "signals" not in marker
    assert marker["privacy"]["label_is_user_supplied"] is True


def test_marker_rejects_empty_and_too_long_values():
    capture = load_capture_module()
    with pytest.raises(ValueError):
        capture.normalize_marker("   ")
    with pytest.raises(ValueError):
        capture.normalize_marker("X" * 81)


def test_append_jsonl_appends_independent_records(tmp_path):
    capture = load_capture_module()
    path = tmp_path / "capture.jsonl"
    capture.append_jsonl(path, {"seq": 1, "value": "первый"})
    capture.append_jsonl(path, {"seq": 2, "value": "второй"})

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0]) == {"seq": 1, "value": "первый"}
    assert json.loads(lines[1]) == {"seq": 2, "value": "второй"}


def test_diagnostics_reader_exports_bounded_session(tmp_path):
    capture = load_capture_module()
    path = tmp_path / "capture.jsonl"
    for seq in range(1, 4):
        capture.append_jsonl(path, {"seq": seq, "type": "refresh"})

    exported = capture.read_jsonl_for_diagnostics(path, max_records=2)
    assert exported["records_in_file"] == 3
    assert exported["records_exported"] == 2
    assert exported["truncated"] is True
    assert [item["seq"] for item in exported["records"]] == [1, 2]
    assert exported["read_error"] is None


def test_diagnostics_reader_reports_invalid_lines(tmp_path):
    capture = load_capture_module()
    path = tmp_path / "capture.jsonl"
    path.write_text('{"seq":1}\nnot-json\n', encoding="utf-8")

    exported = capture.read_jsonl_for_diagnostics(path)
    assert exported["records_in_file"] == 2
    assert exported["records_exported"] == 1
    assert exported["invalid_lines"] == 1
    assert exported["truncated"] is False
