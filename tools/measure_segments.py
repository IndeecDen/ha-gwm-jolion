"""Explain why analyze() splits the track into segments.

Fragmenting the route into many short pieces makes the map look broken, so every
break must be attributable: a real outage, an impossible step, or a source switch.

Run: .venv\\Scripts\\python.exe tools\\measure_segments.py <locator.sqlite>
"""
from __future__ import annotations

import importlib.util
from collections import Counter
import math
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "custom_components" / "gwm_jolion" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    flt = load("locator_filter")
    protocol = load("locator_protocol")
    db = sqlite3.connect(f"file:{Path(sys.argv[1]).as_posix()}?mode=ro", uri=True)
    rows = db.execute(
        "SELECT timestamp_ms, latitude, longitude, accuracy_m, speed_kmh, speed_accuracy_kmh "
        "FROM points ORDER BY timestamp_ms"
    ).fetchall()
    db.close()
    points = [
        {"id": f"p{r[0]}", "timestamp_ms": r[0], "latitude": r[1], "longitude": r[2],
         "accuracy_m": r[3], "speed_kmh": r[4], "speed_accuracy_kmh": r[5],
         "source": "app", "time_known": True, "accuracy_known": True}
        for r in rows
    ]
    filtered = flt.filter_display(points)

    causes = Counter()
    prev = None
    for p in filtered:
        if prev is not None:
            delta = p["timestamp_ms"] - prev["timestamp_ms"]
            meters = protocol.distance(prev, p)
            if p.get("display_break") or prev.get("display_break"):
                causes["display_break"] += 1
            elif delta <= 0:
                causes["время назад"] += 1
            elif delta > 120000:
                causes["провал >2 мин"] += 1
            elif meters / (delta / 1000) > 100:
                causes["невозможная скорость"] += 1
        prev = p

    held = sum(1 for p in filtered if p.get("display_held"))
    pinned = sum(1 for p in filtered if p.get("display_filtered"))
    print(f"точек: {len(filtered)}  удержано на месте: {held}  закреплено к якорю: {pinned}")
    print(f"сегментов: {len(protocol.analyze(filtered)['segments'])}")
    print("\nпричины разрывов:")
    for reason, count in causes.most_common():
        print(f"  {reason:24} {count}")

    # A break is only honest if the drawn line really could not continue.
    print("\nшаг в каждом разрыве, м (сколько всего и сколько крупных):")
    steps = []
    for i, p in enumerate(filtered):
        if not p.get("display_break") or i == 0:
            continue
        previous = filtered[i - 1]
        steps.append(protocol.distance(previous, p))
    if steps:
        steps.sort()
        small = [s for s in steps if s <= 30]
        print(f"  разрывов: {len(steps)}   крупнее 30 м: {len(steps) - len(small)}")
        print(f"  p50 {steps[len(steps)//2]:.1f} м   p90 {steps[int(len(steps)*0.9)]:.1f} м   max {steps[-1]:.1f} м")
    return 0


if __name__ == "__main__":
    sys.exit(main())
