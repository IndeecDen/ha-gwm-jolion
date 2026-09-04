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
