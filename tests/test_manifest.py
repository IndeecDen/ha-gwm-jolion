"""Minimum HA version belongs in HACS metadata, not the integration manifest."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "custom_components/gwm_jolion/manifest.json"


def test_manifest_declares_supported_home_assistant_version():
    metadata = json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))
    minimum = metadata.get("homeassistant")
    assert minimum, "hacs.json must declare a minimum Home Assistant version"
    assert re.fullmatch(r"\d{4}\.\d{1,2}(?:\.\d+)?", minimum), f"unexpected version {minimum!r}"


def test_manifest_version_and_homeassistant_minimum_are_distinct_fields():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert "homeassistant" not in manifest, "hassfest rejects this unsupported manifest field"
    assert manifest["version"] != json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))["homeassistant"]
