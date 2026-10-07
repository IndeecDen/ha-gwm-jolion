"""Strict HA checks; Windows socketpair adaptation lives in tools/run_ha_tests.py."""
import importlib.util
import os

import pytest

STRICT = os.environ.get("GWM_HA_STRICT") == "1"
if STRICT and importlib.util.find_spec("pytest_homeassistant_custom_component") is None:
    raise pytest.UsageError("Install tests/ha/requirements.txt; HA checks cannot be skipped")

pytest.importorskip("pytest_homeassistant_custom_component", reason="needs pytest-homeassistant-custom-component")


def pytest_sessionfinish(session, exitstatus):
    if STRICT:
        reporter = session.config.pluginmanager.get_plugin("terminalreporter")
        if reporter and reporter.stats.get("skipped"):
            session.exitstatus = pytest.ExitCode.TESTS_FAILED
