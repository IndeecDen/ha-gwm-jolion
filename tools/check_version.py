"""Verify the manifest version passes Home Assistant's own loader validation.

Home Assistant validates a custom integration version with AwesomeVersion and an
explicit strategy allow-list (loader.py, resolve_from_root). A version that does
not match any allowed strategy is reported as `unknown` and the integration is
blocked from loading, which later surfaces only as "Integration not found".

Run: .venv\\Scripts\\python.exe tools\\check_version.py
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import sys

from awesomeversion import AwesomeVersion, AwesomeVersionException, AwesomeVersionStrategy

# Exactly the list used by homeassistant.loader.
ALLOWED = [
    AwesomeVersionStrategy.CALVER,
    AwesomeVersionStrategy.SEMVER,
    AwesomeVersionStrategy.SIMPLEVER,
    AwesomeVersionStrategy.BUILDVER,
    AwesomeVersionStrategy.PEP440,
]

# Bundled third-party assets keep their own version and must not follow ours.
VENDOR_VERSIONS = {"1.4.0"}  # vendor/jsQR.js

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "gwm_jolion"


def main() -> int:
    manifest = json.loads((COMPONENT / "manifest.json").read_text(encoding="utf-8"))
    version = manifest["version"]
    found: dict[str, str] = {"manifest.json": version}

    const = (COMPONENT / "const.py").read_text(encoding="utf-8")
    found["const.py"] = re.search(r'VERSION = "([^"]+)"', const).group(1)

    init = (COMPONENT / "__init__.py").read_text(encoding="utf-8")
    # The cache buster is now derived from the manifest instead of being written out
    # per asset. Verify that wiring and reject any leftover hardcoded revision, which
    # is exactly what lets the browser keep serving a stale card.
    if "INTEGRATION_VERSION" not in init or "manifest.json" not in init:
        print("INCONSISTENT: __init__.py does not derive the cache buster from the manifest")
        return 1
    literal = set(re.findall(r"\?v=([0-9A-Za-z.\-]+)", init))
    stale = literal - VENDOR_VERSIONS
    if stale:
        print(f"INCONSISTENT: hardcoded cache-buster(s) in __init__.py: {sorted(stale)}")
        return 1
    found["__init__.py cache-buster"] = version

    found["package.json"] = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))["version"]

    print(f"manifest version: {version}")
    try:
        AwesomeVersion(version, ensure_strategy=ALLOWED)
    except AwesomeVersionException as err:
        print(f"BLOCKED by Home Assistant: {err}")
        return 1
    print("Home Assistant loader check: OK")

    for source, value in found.items():
        print(f"  {source:32} {value}")

    if len(set(found.values())) != 1:
        print("INCONSISTENT: version strings differ between sources")
        return 1
    print("all sources agree")
    return 0


if __name__ == "__main__":
    sys.exit(main())
