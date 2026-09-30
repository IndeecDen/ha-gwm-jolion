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


def test_every_card_reports_the_manifest_version():
    """No card may announce a different version than the integration ships.

    The version used to live in the manifest, in the asset table and in two card
    constants at once. Bumping some of them left the browser on a stale card and no
    test noticed, so the copies are now checked against each other.
    """
    version = json.loads((FRONTEND.parent / "manifest.json").read_text(encoding="utf-8"))["version"]
    declared = {}
    for card in FRONTEND.glob("gwm-jolion*.js"):
        source = card.read_text(encoding="utf-8")
        for marker in ("CARD_VERSION", "VERSION"):
            token = f'const {marker} = "'
            if token in source:
                declared[f"{card.name}:{marker}"] = source.split(token, 1)[1].split('"', 1)[0]
    assert declared, "no card declares a version"
    wrong = {name: value for name, value in declared.items() if value != version}
    assert not wrong, f"cards disagree with manifest {version}: {wrong}"


def test_card_ships_license_and_cache_revision():
    source = (FRONTEND / "gwm-jolion-remote-card.js").read_text(encoding="utf-8")
    version = json.loads((FRONTEND.parent / "manifest.json").read_text(encoding="utf-8"))["version"]
    # The card's own revision must match the manifest. Reading the manifest instead
    # of repeating the number keeps a version bump from failing a packaging test.
    assert f'const CARD_VERSION = "{version}"' in source
    # The integration attaches the cache buster from the manifest, so the URL is not
    # written out in __init__.py to drift. Check the wiring: the version comes from
    # the manifest and the asset is registered through the helper that appends it.
    init_source = (FRONTEND.parent / "__init__.py").read_text(encoding="utf-8")
    assert '"manifest.json"' in init_source and "INTEGRATION_VERSION" in init_source
    assert '_asset("gwm-jolion-remote-card.js"' in init_source
    assert "GNU GENERAL PUBLIC LICENSE" in (FRONTEND / "LICENSE.starline").read_text(encoding="utf-8")
    assert "Anonym-tsk/lovelace-starline-card" in (FRONTEND / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
