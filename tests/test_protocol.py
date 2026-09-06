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


def test_signal_change_history_records_initial_and_changes_only():
    protocol = load_module("gwm_protocol_history_test", "custom_components/gwm_jolion/protocol.py")
    history = []
    last_values = {}

    protocol.update_signal_change_history(
        history,
        last_values,
        {"2220001": 0, "2017002": 35},
        "2026-09-06T15:00:00+00:00",
    )
    assert len(history) == 1
    assert history[0]["code"] == "2220001"
    assert history[0]["value"] == 0
    assert history[0]["initial"] is True

    protocol.update_signal_change_history(
        history,
        last_values,
        {"2220001": 0},
        "2026-09-06T15:01:00+00:00",
    )
    assert len(history) == 1

    protocol.update_signal_change_history(
        history,
        last_values,
        {"2220001": 3},
        "2026-09-06T15:02:00+00:00",
    )
    assert len(history) == 2
    assert history[-1]["previous"] == 0
    assert history[-1]["value"] == 3
    assert history[-1]["initial"] is False


def test_signal_change_history_tracks_unknown_and_is_bounded():
    protocol = load_module("gwm_protocol_history_bound_test", "custom_components/gwm_jolion/protocol.py")
    history = []
    last_values = {}

    protocol.update_signal_change_history(
        history,
        last_values,
        {"9999999": 0},
        "t0",
        max_events=2,
    )
    protocol.update_signal_change_history(
        history,
        last_values,
        {"9999999": 1},
        "t1",
        max_events=2,
    )
    protocol.update_signal_change_history(
        history,
        last_values,
        {"9999999": 2},
        "t2",
        max_events=2,
    )

    assert len(history) == 2
    assert [event["value"] for event in history] == [1, 2]
    assert all(event["key"] == "unknown_signal" for event in history)
