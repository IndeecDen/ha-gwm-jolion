"""List the worst surviving track spikes with their context.

A 1 Hz point pair cannot legitimately cover 174 m. Anything above a plausible
speed is a spike the display filter let through, and it is what makes the track
look jagged on the map.

Run: .venv\\Scripts\\python.exe tools\\measure_spikes.py <path-to-locator.sqlite> [limit]
"""
from __future__ import annotations

import importlib.util
import math
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "locator_filter", ROOT / "custom_components" / "gwm_jolion" / "locator_filter.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
filter_display = module.filter_display


def meters(a, b) -> float:
    lat1, lat2 = math.radians(a[0]), math.radians(b[0])
    dlat = lat2 - lat1
    dlon = math.radians(b[1] - a[1])
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371000 * 2 * math.asin(math.sqrt(min(1, h)))


def main() -> int:
    path = Path(sys.argv[1])
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 12
    db = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    rows = db.execute(
        "SELECT timestamp_ms, latitude, longitude, accuracy_m, speed_kmh, speed_accuracy_kmh "
        "FROM points ORDER BY timestamp_ms"
    ).fetchall()
    db.close()

    points = [
        {"timestamp_ms": r[0], "latitude": r[1], "longitude": r[2], "accuracy_m": r[3],
         "speed_kmh": r[4], "speed_accuracy_kmh": r[5], "source": "app", "id": f"p{r[0]}"}
        for r in rows
    ]
    legs, current = [], []
    for p in points:
        if current and p["timestamp_ms"] - current[-1]["timestamp_ms"] > 30000:
            legs.append(current)
            current = []
        current.append(p)
    if current:
        legs.append(current)
    displayed = []
    for leg in legs:
        displayed.extend(filter_display(leg))

    spikes = []
    across_break = 0
    for index, (a, b) in enumerate(zip(displayed, displayed[1:])):
        dt = (b["timestamp_ms"] - a["timestamp_ms"]) / 1000
        if not 0 < dt <= 10:
            continue
        d = meters((a["latitude"], a["longitude"]), (b["latitude"], b["longitude"]))
        implied = d / dt * 3.6
        if implied <= 130:
            continue
        # A step across a display break is not drawn as a line: the card shows a
        # dashed gap there, which is the honest representation of lost track.
        if b.get("display_break") or a.get("display_break"):
            across_break += 1
            continue
        spikes.append((implied, d, dt, a, b, index))
    spikes.sort(reverse=True, key=lambda s: s[0])

    print(f"нарисованных линий с невозможной скоростью >130 км/ч: {len(spikes)}")
    print(f"шагов через разрыв (линия не рисуется, показывается пунктир): {across_break}\n")
    print(f"{'км/ч':>8} {'м':>7} {'с':>5} {'acc_b':>7} {'spd_b':>7} {'закреп':>7} {'разрыв':>7}")
    for implied, d, dt, a, b, index in spikes[:limit]:
        print(
            f"{implied:8.0f} {d:7.0f} {dt:5.1f} {b['accuracy_m']:7.1f} "
            f"{(b['speed_kmh'] if b['speed_kmh'] is not None else -1):7.1f} "
            f"{str(bool(b.get('display_filtered'))):>7} {str(bool(b.get('display_break'))):>7}"
        )
        # Show the raw points around the worst one so the cause is visible.
        if spikes and implied == spikes[0][0]:
            print("\n  контекст (точки в отфильтрованном потоке):")
            for k in range(max(0, index - 3), min(len(displayed), index + 5)):
                p = displayed[k]
                mark = " <-- скачок из" if k == index else (" <-- приём" if k == index + 1 else "")
                print(
                    f"    [{k:5}] dt={(p['timestamp_ms'] - displayed[k-1]['timestamp_ms']) / 1000 if k else 0:5.1f}с "
                    f"acc={p['accuracy_m']:6.1f} spd={(p['speed_kmh'] if p['speed_kmh'] is not None else -1):6.2f} "
                    f"фильтр={str(bool(p.get('display_filtered'))):5} "
                    f"разрыв={str(bool(p.get('display_break'))):5}{mark}"
                )
            limit = module.step_limit(a, b, dt)
            print(f"\n  что решил фильтр: step_limit={limit:.1f} м, шаг={d:.1f} м, "
                  f"якорь={module.anchored_hold(a)}, прошло={d <= limit}")
            same_leg = not a.get("display_break") and not b.get("display_break")
            print(f"  обе точки в одном непрерывном отрезке: {same_leg}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
