from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def load_command_safety():
    path = ROOT / "custom_components/gwm_jolion/command_safety.py"
    spec = importlib.util.spec_from_file_location("gwm_command_safety_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["gwm_command_safety_test"] = module
    spec.loader.exec_module(module)
    return module


def test_auth_error_codes() -> None:
    command_safety = load_command_safety()
    for code in ("401", "401000", "308001", "308002", "308003"):
        assert command_safety.is_auth_error_code(code)
    assert not command_safety.is_auth_error_code("000000")
    assert not command_safety.is_auth_error_code("1000")


def test_t5_result_classification() -> None:
    command_safety = load_command_safety()

    for code in ("0", "6", "10"):
        assert command_safety.classify_t5_result_code(code) == "success"
    for code in ("1000", "2000", "11"):
        assert command_safety.classify_t5_result_code(code) == "pending"

    assert command_safety.classify_t5_result_code("") == "unknown"
    assert command_safety.classify_t5_result_code(None) == "unknown"
    assert command_safety.classify_t5_result_code("12345") == "error"
    assert command_safety.classify_t5_result_code("network_error") == "error"


def test_remote_start_blockers() -> None:
    command_safety = load_command_safety()

    assert command_safety.remote_start_block_reason({"engine_running": True}) == "двигатель уже работает"
    assert command_safety.remote_start_block_reason({"vehicle_unlocked": True}) == "автомобиль не закрыт"
    assert command_safety.remote_start_block_reason({"doors_open": True}) == "открыта одна или несколько дверей"
    assert command_safety.remote_start_block_reason({"trunk_open": True}) == "открыт багажник"


def test_remote_start_allows_safe_or_unknown_state() -> None:
    command_safety = load_command_safety()

    assert command_safety.remote_start_block_reason({
        "engine_running": False,
        "vehicle_unlocked": False,
        "doors_open": False,
        "trunk_open": False,
    }) is None
    assert command_safety.remote_start_block_reason({}) is None
    assert command_safety.remote_start_block_reason(None) is None
