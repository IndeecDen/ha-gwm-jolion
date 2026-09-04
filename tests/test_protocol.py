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


def test_protocol_registry_has_unique_consistent_codes():
    protocol = load_module("gwm_protocol_test", "custom_components/gwm_jolion/protocol.py")
    assert protocol.SIGNALS
    assert all(code == info.code for code, info in protocol.SIGNALS.items())
    assert len(protocol.SIGNALS) == len(set(protocol.SIGNALS))


def test_core_confirmed_codes_are_present():
    protocol = load_module("gwm_protocol_core_test", "custom_components/gwm_jolion/protocol.py")
    confirmed = {
        code
        for code, info in protocol.SIGNALS.items()
        if info.status == protocol.VerificationStatus.CONFIRMED
    }
    for code in {"2016001", "2208001", "2206001", "2210001", "2210002", "2210003", "2210004"}:
        assert code in confirmed


def test_signal_report_marks_observed_codes():
    protocol = load_module("gwm_protocol_report_test", "custom_components/gwm_jolion/protocol.py")
    report = protocol.signal_report({"2016001", "2208001"})
    assert report["2016001"]["observed"] is True
    assert report["2208001"]["observed"] is True
    assert report["2202001"]["observed"] is False
