"""Reproduce the trips card failure on the real archive.

The card only reports "история поездок недоступна" when _query raises, so this
replays the same call with cloud and app points mixed, the way production does.

Run: .venv\\Scripts\\python.exe tools\\repro_trips.py <locator.sqlite> <trips.sqlite>
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sqlite3
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "gwm_jolion"


def load(name, namespace=None):
    spec = importlib.util.spec_from_file_location(name, COMPONENT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    if namespace:
        spec.loader.exec_module(module, namespace)
    else:
        spec.loader.exec_module(module)
    return module


def main() -> int:
    protocol = load("locator_protocol")
    merge_src = (COMPONENT / "locator.py").read_text(encoding="utf-8")
    start = merge_src.index("def merge_inferred_parking")
    end = merge_src.index("class HybridHistory")
    namespace = {"analyze": protocol.analyze}
    exec(compile(merge_src[start:end], "locator.py", "exec"), namespace)
    merge = namespace["merge_inferred_parking"]

    app = sqlite3.connect(f"file:{Path(sys.argv[1]).as_posix()}?mode=ro", uri=True)
    rows = app.execute(
        "SELECT timestamp_ms, latitude, longitude, accuracy_m, speed_kmh, speed_accuracy_kmh "
        "FROM points ORDER BY timestamp_ms"
    ).fetchall()
    app.close()
    cloud = sqlite3.connect(f"file:{Path(sys.argv[2]).as_posix()}?mode=ro", uri=True)
    cloud_rows = cloud.execute(
        "SELECT ts, lat, lon, odo FROM points WHERE lat IS NOT NULL ORDER BY ts"
    ).fetchall()
    cloud.close()

    app_points = [
        {"id": f"p{r[0]}", "timestamp_ms": r[0], "latitude": r[1], "longitude": r[2],
         "accuracy_m": r[3], "speed_kmh": r[4], "speed_accuracy_kmh": r[5],
         "source": "app", "time_known": True, "accuracy_known": True}
        for r in rows
    ]
    # cloud_point() in locator_merge is what production produces, accuracy unknown.
    merge_mod = load("locator_merge")
    cloud_points = [merge_mod.cloud_point(ts, {"latitude": lat, "longitude": lon})
                    for ts, lat, lon, _ in cloud_rows]
    cloud_points = [p for p in cloud_points if p]

    print(f"точек приложения: {len(app_points)}, облака: {len(cloud_points)}")
    print("accuracy_m у облачных точек:", {p["accuracy_m"] for p in cloud_points[:50]})

    merged = sorted([*app_points, *cloud_points], key=lambda p: p["timestamp_ms"])
    mileage = [(ts, None, None, odo) for ts, _, _, odo in cloud_rows if odo is not None]
    print(f"смешанный поток: {len(merged)} точек, пробегов: {len(mileage)}")

    try:
        spots = merge([], merged, mileage)
        print(f"OK: parking_spots = {len(spots)}")
    except Exception:
        print("\nИСКЛЮЧЕНИЕ — именно оно ломает карточку:")
        traceback.print_exc()
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
