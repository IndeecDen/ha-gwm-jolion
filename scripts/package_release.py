"""Build local release archives from this checkout; never uploads anything."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "gwm_jolion"
VERSION = json.loads((COMPONENT / "manifest.json").read_text(encoding="utf-8"))["version"]
APK_VERSION = (ROOT / "android" / "app" / "build.gradle").read_text(encoding="utf-8")
if f"versionName '{VERSION}'" not in APK_VERSION:
    raise SystemExit("HA and Android versions differ")

APK = ROOT / "android" / "app" / "build" / "outputs" / "apk" / "release" / "app-release.apk"
if not APK.is_file():
    raise SystemExit(f"Build the signed Android release APK first: {APK}")

# Packaging must not silently ship an APK predating the Android changes.
android_inputs = [ROOT / "android" / "build.gradle", ROOT / "android" / "app" / "build.gradle"]
android_inputs.extend(p for p in (ROOT / "android" / "app" / "src" / "main").rglob("*") if p.is_file())
if any(p.stat().st_mtime_ns > APK.stat().st_mtime_ns for p in android_inputs):
    raise SystemExit("Android sources are newer than the APK. Run assembleRelease before packaging.")

OUT = ROOT / "dist"
OUT.mkdir(exist_ok=True)
safe_version = re.sub(r"[^0-9A-Za-z._-]", "_", VERSION)
apk_out = OUT / f"Jolion.Locator.{safe_version}.apk"
apk_out.write_bytes(APK.read_bytes())

ha_out = OUT / f"ha-gwm-jolion-{VERSION}.zip"
with zipfile.ZipFile(ha_out, "w", zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(COMPONENT.rglob("*")):
        if path.is_file() and not any(part == "__pycache__" for part in path.parts) and path.suffix != ".pyc":
            archive.write(path, path.relative_to(ROOT).as_posix())

bundle_out = OUT / f"ha-gwm-jolion-{VERSION}-bundle.zip"
with zipfile.ZipFile(bundle_out, "w", zipfile.ZIP_DEFLATED) as archive:
    archive.write(apk_out, apk_out.name)
    archive.write(ha_out, ha_out.name)
    for name in ("README.md", "CHANGELOG.md", "THIRD_PARTY_NOTICES.md", "LICENSE", "docs/golion-locator.md", "docs/golion-locator-yandex.md", "docs/diagnostics.md"):
        archive.write(ROOT / name, name)

outputs = (apk_out, ha_out, bundle_out)
(OUT / "SHA256SUMS.txt").write_text(
    "".join(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n" for path in outputs),
    encoding="utf-8",
)
for path in outputs:
    print(path)
print(OUT / "SHA256SUMS.txt")
