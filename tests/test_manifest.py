"""The manifest declares a minimum Home Assistant version.

`config_flow` subclasses `OptionsFlowWithReload`, which appeared in Home Assistant
2025.7 (PR #146910). On an older core the config flow fails with a bare
`AttributeError` instead of a clear message, so the minimum is stated in the
manifest and kept under test.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "custom_components/gwm_jolion/manifest.json"


def test_manifest_declares_supported_home_assistant_version():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    minimum = manifest.get("homeassistant")
    assert minimum, "manifest.json must declare a minimum Home Assistant version"
    assert re.fullmatch(r"\d{4}\.\d{1,2}(?:\.\d+)?", minimum), f"unexpected version {minimum!r}"


def test_manifest_version_and_homeassistant_minimum_are_distinct_fields():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["version"] != manifest["homeassistant"], (
        "integration version and minimum core version are different things"
    )
