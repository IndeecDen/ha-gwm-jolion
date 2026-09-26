from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types

ROOT = Path(__file__).resolve().parents[1]
PKG = "gwm_helpers_testpkg"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_helpers():
    pkg = types.ModuleType(PKG)
    pkg.__path__ = [str(ROOT / "custom_components/gwm_jolion")]
    sys.modules[PKG] = pkg

    if "homeassistant.exceptions" not in sys.modules:
        ha = types.ModuleType("homeassistant")
        exc = types.ModuleType("homeassistant.exceptions")
        exc.ConfigEntryAuthFailed = type("ConfigEntryAuthFailed", (Exception,), {})
        sys.modules.setdefault("homeassistant", ha)
        sys.modules["homeassistant.exceptions"] = exc

    base = ROOT / "custom_components/gwm_jolion"
    _load(f"{PKG}.const", base / "const.py")
    _load(f"{PKG}.vehicle_data", base / "vehicle_data.py")
    _load(f"{PKG}.vehicle_basics", base / "vehicle_basics.py")
    return _load(f"{PKG}.helpers", base / "helpers.py")


def _status(values: dict[str, int]) -> dict:
    return {"items": [{"code": code, "value": value} for code, value in values.items()]}


def test_window_binary_decoder_accepts_captured_multistate_values() -> None:
    helpers = load_helpers()

    closed = helpers.build_state(_status({"2210001": 1, "2210002": 1, "2210003": 1, "2210004": 1}), {}, {})
    partial = helpers.build_state(_status({"2210001": 3, "2210002": 1, "2210003": 1, "2210004": 1}), {}, {})
    full = helpers.build_state(_status({"2210001": 2, "2210002": 2, "2210003": 2, "2210004": 2}), {}, {})

    assert closed["windows_open"] is False
    assert closed["window_2210001_open"] is False
    assert partial["windows_open"] is True
    assert partial["window_2210001_open"] is True
    assert full["windows_open"] is True
    assert full["window_2210001_open"] is True
    assert full["window_2210002_open"] is True
    assert full["window_2210003_open"] is True
    assert full["window_2210004_open"] is True


def test_unknown_window_raw_value_stays_unknown() -> None:
    helpers = load_helpers()
    state = helpers.build_state(_status({"2210001": 0}), {}, {})
    assert state["windows_open"] is None
    assert state["window_2210001_open"] is None


def test_vehicle_basics_seat_presets_do_not_fake_live_heat_state() -> None:
    helpers = load_helpers()
    state = helpers.build_state({}, {}, {"leftFrontSeat": 3, "rightFrontSeat": 3})

    assert "driver_seat_heat_level_raw" not in state
    assert "passenger_seat_heat_level_raw" not in state


def test_live_seat_heat_signals_remain_authoritative() -> None:
    helpers = load_helpers()
    state = helpers.build_state(
        _status({"2220001": 2, "2220002": 1}),
        {},
        {"leftFrontSeat": 3, "rightFrontSeat": 3},
    )

    assert state["driver_seat_heat_level_raw"] == 2
    assert state["passenger_seat_heat_level_raw"] == 1


def test_tpms_pressure_warning_per_wheel_and_unknown_values():
    helpers = load_helpers()
    wheels = ("fl", "fr", "rl", "rr")
    # Captured FR alert must not flag the other wheels or depend on pressure.
    state = helpers.build_state(_status({"2102001": "0", "2102002": "1", "2102003": 0, "2102004": 0, "2101002": 218.2275}), {})
    assert [state[f"tire_{w}_pressure_warning"] for w in wheels] == [False, True, False, False]
    for code, wheel in zip(range(2102001, 2102005), wheels):
        for raw, expected in [(0, False), (1, True), (2, None), (255, None), (None, None), ("bad", None)]:
            decoded = helpers.build_state(_status({str(code): raw}), {})
            assert decoded[f"tire_{wheel}_pressure_warning"] is expected
            assert all(decoded[f"tire_{other}_pressure_warning"] is None for other in wheels if other != wheel)
    cleared = helpers.build_state(_status({"2102002": 0}), {})
    assert cleared["tire_fr_pressure_warning"] is False
