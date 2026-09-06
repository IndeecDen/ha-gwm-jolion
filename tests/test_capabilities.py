from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, relative: str):
    path = ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_capability_keys_are_consistent():
    capabilities = load_module("gwm_capabilities_test", "custom_components/gwm_jolion/capabilities.py")
    assert capabilities.CAPABILITIES
    assert all(key == item.key for key, item in capabilities.CAPABILITIES.items())


def test_capability_report_observes_telemetry():
    capabilities = load_module("gwm_capabilities_report_test", "custom_components/gwm_jolion/capabilities.py")
    report = capabilities.capability_report({"2016001", "2208001"})
    assert report["engine"]["telemetry_observed"] is True
    assert report["central_lock"]["telemetry_observed"] is True
    assert report["front_windscreen_heat"]["telemetry_observed"] is False
    assert report["engine"]["status"] == "confirmed"


def test_manual_capabilities_preserve_legacy_defaults():
    capabilities = load_module("gwm_capabilities_defaults_test", "custom_components/gwm_jolion/capabilities.py")
    flags = capabilities.resolve_manual_capabilities({})
    assert flags
    assert all(flags.values())


def test_manual_capabilities_can_disable_optional_equipment():
    capabilities = load_module("gwm_capabilities_disable_test", "custom_components/gwm_jolion/capabilities.py")
    flags = capabilities.resolve_manual_capabilities({
        "feature_sunroof": False,
        "feature_sunshade": False,
        "feature_steering_wheel_heat": True,
    })
    assert flags["sunroof"] is False
    assert flags["sunshade"] is False
    assert flags["steering_wheel_heat"] is True


def test_command_and_state_capability_mapping():
    capabilities = load_module("gwm_capabilities_mapping_test", "custom_components/gwm_jolion/capabilities.py")
    assert capabilities.capability_for_command("open_sunroof") == "sunroof"
    assert capabilities.capability_for_command("steering_wheel_heat_on") == "steering_wheel_heat"
    assert capabilities.capability_for_command("flash_lights") is None
    assert capabilities.capability_for_state_key("driver_seat_heat_level_raw") == "seat_heat_driver"
    assert capabilities.capability_for_state_key("front_windscreen_heat_on") == "front_windscreen_heat"


def test_capability_report_includes_manual_enabled_state():
    capabilities = load_module("gwm_capabilities_enabled_test", "custom_components/gwm_jolion/capabilities.py")
    report = capabilities.capability_report(set(), {"sunroof": False, "sunshade": True})
    assert report["sunroof"]["enabled"] is False
    assert report["sunshade"]["enabled"] is True
    assert report["engine"]["enabled"] is True
