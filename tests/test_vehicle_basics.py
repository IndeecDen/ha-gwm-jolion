from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def load_vehicle_basics():
    path = ROOT / "custom_components/gwm_jolion/vehicle_basics.py"
    spec = importlib.util.spec_from_file_location("gwm_vehicle_basics_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["gwm_vehicle_basics_test"] = module
    spec.loader.exec_module(module)
    return module


def test_snapshot_reads_data_config_shape() -> None:
    vehicle_basics = load_vehicle_basics()
    payload = {
        "data": {
            "config": {
                "airConditionerTemperature": "22",
                "leftFrontSeat": 3,
                "rightFrontSeat": 2,
                "shadeScreen": 1,
                "skyLight": 2,
                "steeringWheelHeatingTime": "600",
                "frontWindshieldFullScreenHeatingTime": "900",
                "vin": "SECRET-VIN",
                "userId": "SECRET-USER",
            },
            "subscribe": "opaque-subscription-value",
        }
    }

    snapshot = vehicle_basics.vehicle_basics_snapshot(payload)

    assert snapshot["airConditionerTemperature"] == "22"
    assert snapshot["leftFrontSeat"] == 3
    assert snapshot["rightFrontSeat"] == 2
    assert snapshot["shadeScreen"] == 1
    assert snapshot["skyLight"] == 2
    assert snapshot["steeringWheelHeatingTime"] == "600"
    assert snapshot["frontWindshieldFullScreenHeatingTime"] == "900"
    assert "vin" not in snapshot
    assert "userId" not in snapshot
    assert "subscribe" not in snapshot
    assert "SECRET-VIN" not in repr(snapshot)
    assert "SECRET-USER" not in repr(snapshot)


def test_snapshot_reads_raw_data_config_shape_from_api() -> None:
    vehicle_basics = load_vehicle_basics()
    raw_data = {
        "config": {
            "frontDefrostStatus": 2,
            "backDefrostStatus": 2,
            "frontDefrostTime": "900",
            "rearDefrostTime": "600",
            "leftFrontWindow": 1,
            "rightFrontWindow": 1,
            "leftBackWindow": 1,
            "rightBackWindow": 1,
        }
    }

    snapshot = vehicle_basics.vehicle_basics_snapshot(raw_data)

    assert snapshot == {
        "backDefrostStatus": 2,
        "frontDefrostStatus": 2,
        "frontDefrostTime": "900",
        "leftBackWindow": 1,
        "leftFrontWindow": 1,
        "rearDefrostTime": "600",
        "rightBackWindow": 1,
        "rightFrontWindow": 1,
    }


def test_unknown_nested_fields_are_not_exported() -> None:
    vehicle_basics = load_vehicle_basics()
    payload = {
        "config": {
            "airConditionerStatusTime": "900",
            "someFutureSecret": "must-not-leak",
        }
    }

    snapshot = vehicle_basics.vehicle_basics_snapshot(payload)

    assert snapshot == {"airConditionerStatusTime": "900"}
