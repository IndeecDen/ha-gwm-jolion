from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def load_vehicle_data():
    path = ROOT / "custom_components/gwm_jolion/vehicle_data.py"
    spec = importlib.util.spec_from_file_location("gwm_vehicle_data_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["gwm_vehicle_data_test"] = module
    spec.loader.exec_module(module)
    return module


def test_normalize_jolion_metadata() -> None:
    vehicle_data = load_vehicle_data()
    vehicle = {
        "brandName": "HAVAL",
        "vtype": "JOLION",
        "modelName": "HavalA01_CC7150BA01B_Basic model_High",
        "modelCode": "HavalA01_CC7150BA01B_Basic model_High",
        "engineType": "GW4G15K",
        "tankCapacity": 55.0,
        "config": "High",
        "belongPlatform": "beantech",
        "color": "Ayers Grey",
    }

    result = vehicle_data.normalize_vehicle_metadata(vehicle)

    assert result["brand"] == "HAVAL"
    assert result["model"] == "Haval Jolion"
    assert result["vehicle_type"] == "JOLION"
    assert result["engine_type"] == "GW4G15K"
    assert result["tank_capacity_l"] == 55
    assert result["vehicle_config"] == "High"
    assert result["telematics_platform"] == "beantech"
    assert result["color"] == "Ayers Grey"


def test_calculate_fuel_percent() -> None:
    vehicle_data = load_vehicle_data()
    assert vehicle_data.calculate_fuel_percent(45, 55) == 82
    assert vehicle_data.calculate_fuel_percent("27.5", "55") == 50
    assert vehicle_data.calculate_fuel_percent(60, 55) == 100
    assert vehicle_data.calculate_fuel_percent(-1, 55) == 0
    assert vehicle_data.calculate_fuel_percent(10, 0) is None
    assert vehicle_data.calculate_fuel_percent(None, 55) is None


def test_describe_structure_does_not_expose_values() -> None:
    vehicle_data = load_vehicle_data()
    payload = {
        "code": "000000",
        "data": {
            "vehicleBasicsInfo": {
                "airConditionerTemperature": "22",
                "vin": "SECRET-VIN",
            }
        },
    }

    structure = vehicle_data.describe_structure(payload)
    rendered = repr(structure)

    assert "vehicleBasicsInfo" in rendered
    assert "airConditionerTemperature" in rendered
    assert "vin" in rendered
    assert "000000" not in rendered
    assert "SECRET-VIN" not in rendered
    assert "22" not in rendered
