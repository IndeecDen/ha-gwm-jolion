"""Offline release preflight. Does not upload or modify GitHub."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
CERTIFICATE = "9abac96367ce8227b308709e5eb92e6bf716cc366308628c1d2a4cf22c36b8a6"


def validate_metadata(version, tag, code, previous_code):
    if tag.removeprefix("v") != version:
        raise ValueError("Release tag and manifest version differ")
    if code <= previous_code:
        raise ValueError("APK versionCode must be greater than the previous published code")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--previous-code", type=int, required=True)
    parser.add_argument("--build-tools", type=Path, help="Android SDK build-tools/35.0.0")
    args = parser.parse_args()
    version = json.loads((ROOT / "custom_components/gwm_jolion/manifest.json").read_text(encoding="utf-8"))["version"]
    gradle = (ROOT / "android/app/build.gradle").read_text(encoding="utf-8")
    code = int(re.search(r"versionCode\s+(\d+)", gradle)[1])
    validate_metadata(version, args.tag, code, args.previous_code)
    if re.search(r"versionName\s+'([^']+)'", gradle)[1] != version:
        raise ValueError("Android and HA versions differ")
    sdk = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
    tools = args.build_tools or (Path(sdk) / "build-tools/35.0.0" if sdk else None)
    if tools is None:
        raise ValueError("Set ANDROID_HOME or --build-tools")
    apk = ROOT / "dist" / f"Jolion.Locator.{version}.apk"
    suffix = ".bat" if os.name == "nt" else ""
    signed = subprocess.check_output([str(tools / ("apksigner" + suffix)), "verify", "--verbose", "--print-certs", str(apk)], text=True)
    if f"Signer #1 certificate SHA-256 digest: {CERTIFICATE}" not in signed or "Number of signers: 1" not in signed:
        raise ValueError("Unexpected APK signing certificate")
    aapt = tools / ("aapt.exe" if os.name == "nt" else "aapt")
    metadata = subprocess.check_output([str(aapt), "dump", "badging", str(apk)], text=True)
    for expected in ("name='ru.jolion.locator'", f"versionCode='{code}'", f"versionName='{version}'", "sdkVersion:'27'", "targetSdkVersion:'28'"):
        if expected not in metadata:
            raise ValueError(f"APK metadata mismatch: {expected}")
    sums = dict(line.split("  ", 1)[::-1] for line in (ROOT / "dist/SHA256SUMS.txt").read_text(encoding="utf-8").splitlines() if line)
    for name in (apk.name, f"ha-gwm-jolion-{version}.zip", f"ha-gwm-jolion-{version}-bundle.zip"):
        file = ROOT / "dist" / name
        if hashlib.sha256(file.read_bytes()).hexdigest() != sums.get(name):
            raise ValueError(f"Checksum mismatch: {name}")
        with zipfile.ZipFile(file) as archive:
            if archive.testzip():
                raise ValueError(f"Archive CRC failure: {name}")
            if name.endswith(".apk") and any(path.startswith("lib/") for path in archive.namelist()):
                raise ValueError("Unexpected native libraries in Java-only APK")
    print(f"Release preflight OK: {version}, versionCode {code}, signature and all checksums verified")


if __name__ == "__main__":
    main()
