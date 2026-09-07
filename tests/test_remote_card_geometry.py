"""Packaging checks; runtime behavior is covered by remote_card_browser.cjs."""
import base64
import json
from pathlib import Path

FRONTEND = Path("custom_components/gwm_jolion/frontend")


def test_embedded_artwork_is_complete_and_valid_png():
    source = (FRONTEND / "gwm-jolion-remote-card.js").read_text(encoding="utf-8")
    assets, _ = json.JSONDecoder().raw_decode(source.split("const STARLINE_ASSETS = ", 1)[1])
    for theme in ("", "_dark"):
        for name in ("bg_guard", "door", "hood", "trunk", "frontlight", "key",
                     "sectors_1", "sectors_2", "sectors_3", "smoke_1", "smoke_2", "smoke_3"):
            data = base64.b64decode(assets[name + theme].split(",", 1)[1], validate=True)
            assert data.startswith(b"\x89PNG\r\n\x1a\n")


def test_card_ships_license_and_cache_revision():
    source = (FRONTEND / "gwm-jolion-remote-card.js").read_text(encoding="utf-8")
    version = source.split('const CARD_VERSION = "', 1)[1].split('"', 1)[0]
    assert f"gwm-jolion-remote-card.js?v={version}" in (FRONTEND.parent / "__init__.py").read_text(encoding="utf-8")
    assert "GNU GENERAL PUBLIC LICENSE" in (FRONTEND / "LICENSE.starline").read_text(encoding="utf-8")
    assert "Anonym-tsk/lovelace-starline-card" in (FRONTEND / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
