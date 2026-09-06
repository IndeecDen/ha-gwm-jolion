from __future__ import annotations

from datetime import datetime, timezone
import json

from custom_components.gwm_jolion.protocol_capture import append_jsonl, build_capture_record


def test_capture_baseline_contains_full_snapshots_without_changes(tmp_path):
    record = build_capture_record(
        sequence=1,
        timestamp=datetime(2026, 9, 6, 16, 0, tzinfo=timezone.utc),
        source="poll",
        integration_version="test",
        signals={"2220001": 0, "9999999": 7},
        previous_signals={},
        unknown_signals={"9999999": 7},
        vehicle_basics={"leftFrontSeat": 0},
        previous_vehicle_basics={},
    )

    assert record["baseline"] is True
    assert record["signals"]["2220001"] == 0
    assert record["unknown_signals"] == {"9999999": 7}
    assert record["changes"] == []
    assert record["vehicle_basics_changes"] == []
    assert record["privacy"]["contains_vin"] is False


def test_capture_diff_has_known_and_unknown_signal_metadata():
    record = build_capture_record(
        sequence=2,
        timestamp=datetime(2026, 9, 6, 16, 1, tzinfo=timezone.utc),
        source="manual_button",
        integration_version="test",
        signals={"2220001": 3, "9999999": 8},
        previous_signals={"2220001": 0, "9999999": 7},
        unknown_signals={"9999999": 8},
        vehicle_basics={"leftFrontSeat": 3},
        previous_vehicle_basics={"leftFrontSeat": 0},
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


def test_append_jsonl_appends_independent_records(tmp_path):
    path = tmp_path / "capture.jsonl"
    append_jsonl(path, {"seq": 1, "value": "первый"})
    append_jsonl(path, {"seq": 2, "value": "второй"})

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0]) == {"seq": 1, "value": "первый"}
    assert json.loads(lines[1]) == {"seq": 2, "value": "второй"}
