from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_field_confirmed_window_positions_and_climate() -> None:
    protocol = _load("gwm_protocol_alpha19_7", "custom_components/gwm_jolion/protocol.py")
    assert protocol.SIGNALS["2210001"].description == "Окно переднее левое / водительское"
    assert protocol.SIGNALS["2210002"].description == "Окно переднее правое"
    assert protocol.SIGNALS["2210003"].description == "Окно заднее левое"
    assert protocol.SIGNALS["2210004"].description == "Окно заднее правое"
    for code in ("2210001", "2210002", "2210003", "2210004", "2202001"):
        assert protocol.SIGNALS[code].status == protocol.VerificationStatus.CONFIRMED


def test_high_beam_code_remains_candidate_not_confirmed() -> None:
    protocol = _load("gwm_protocol_light_alpha19_7", "custom_components/gwm_jolion/protocol.py")
    info = protocol.SIGNALS["2204008"]
    assert info.status == protocol.VerificationStatus.KNOWN_UNVERIFIED
    assert "дальнего света" in info.description.lower()
    assert "LIGHT_HIGH" in info.notes


def test_const_exposes_raw_sensors_with_physical_names() -> None:
    const = _load("gwm_const_alpha19_7", "custom_components/gwm_jolion/const.py")
    assert const.VERSION == "0.1.0-alpha.19.7"
    assert const.RAW_SENSOR_MAP["2210001"].name == "Окно переднее левое (raw)"
    assert const.RAW_SENSOR_MAP["2210002"].name == "Окно переднее правое (raw)"
    assert const.RAW_SENSOR_MAP["2210003"].name == "Окно заднее левое (raw)"
    assert const.RAW_SENSOR_MAP["2210004"].name == "Окно заднее правое (raw)"
