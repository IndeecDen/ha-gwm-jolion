"""Decide, for every long transmission gap, whether the car stood still.

Three independent signals are compared for the points on each side of the gap:
  * GPS cluster spread - is the parked position tight, or is the GPS jumping?
  * the cloud odometer - did the car actually roll, independently of GPS?
  * where the track goes after the gap - a clean departing track, or noise?

Run: .venv\\Scripts\\python.exe tools\\measure_gap_context.py <locator.sqlite> <trips.sqlite>
"""
from __future__ import annotations

import math
from pathlib import Path
import sqlite3
import statistics
import sys

WINDOW = 60          # points examined on each side of a gap
MIN_GAP_S = 600      # only gaps of 10 minutes and longer


def meters(a, b) -> float:
    lat1, lat2 = math.radians(a[0]), math.radians(b[0])
    dlat = lat2 - lat1
    dlon = math.radians(b[1] - a[1])
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371000 * 2 * math.asin(math.sqrt(min(1, h)))


def cluster(points):
    """Return (radius_p50, radius_max, mean_accuracy, biggest_step) for a run."""
    if len(points) < 2:
        return None
    lat0 = statistics.fmean(p[1] for p in points)
    lon0 = statistics.fmean(p[2] for p in points)
    radii = sorted(meters((lat0, lon0), (p[1], p[2])) for p in points)
    steps = [
        meters((a[1], a[2]), (b[1], b[2]))
        for a, b in zip(points, points[1:])
        if 0 < (b[0] - a[0]) / 1000 <= 10
    ]
    acc = [p[3] for p in points if p[3] is not None]
    return (
        radii[len(radii) // 2],
        radii[-1],
        statistics.fmean(acc) if acc else None,
        max(steps) if steps else 0.0,
    )


def odo_at(odometer, when_ms):
    """Odometer reading closest to a moment, from the cloud archive."""
    if not odometer:
        return None
    best = min(odometer, key=lambda t: abs(t - when_ms))
    return odometer[best], abs(best - when_ms) / 1000


def main() -> int:
    app_db = sqlite3.connect(f"file:{Path(sys.argv[1]).as_posix()}?mode=ro", uri=True)
    app = app_db.execute(
        "SELECT timestamp_ms, latitude, longitude, accuracy_m, speed_kmh FROM points "
        "ORDER BY timestamp_ms"
    ).fetchall()
    app_db.close()

    cloud = {}
    if len(sys.argv) > 2:
        try:
            c_db = sqlite3.connect(f"file:{Path(sys.argv[2]).as_posix()}?mode=ro", uri=True)
            for ts, odo in c_db.execute(
                "SELECT ts, odo FROM points WHERE odo IS NOT NULL ORDER BY ts"
            ):
                cloud[int(ts * 1000)] = odo
            c_db.close()
        except Exception as err:  # noqa: BLE001 - diagnostics only
            print(f"(облачный архив не прочитан: {err})")
    print(f"показаний одометра в облачном архиве: {len(cloud)}\n")

    for a, b in zip(app, app[1:]):
        dt = (b[0] - a[0]) / 1000
        if dt < MIN_GAP_S:
            continue
        before = app[max(0, a[0] and app.index(a) - WINDOW + 1): app.index(a) + 1]
        after = app[app.index(b): app.index(b) + WINDOW]
        cb = cluster(before)
        ca = cluster(after)
        jump = meters((a[1], a[2]), (b[1], b[2]))
        # Comparing the two boundary points overstates the displacement whenever the
        # cluster after a gap is noisy, so also compare cluster centroids.
        pre_c = (statistics.fmean(p[1] for p in before), statistics.fmean(p[2] for p in before))
        post_c = (statistics.fmean(p[1] for p in after), statistics.fmean(p[2] for p in after))
        centroid_jump = meters(pre_c, post_c)
        ob, ob_dt = odo_at(cloud, a[0])
        oa, oa_dt = odo_at(cloud, b[0])

        print("=" * 74)
        print(f"разрыв {dt / 3600:.2f} ч, возобновление через {jump:.0f} м "
              f"(по центрам групп: {centroid_jump:.0f} м)")
        print(f"  ДО:  разброс p50 {cb[0]:6.1f} м  max {cb[1]:6.1f} м  "
              f"точность ~{cb[2]:.1f} м  макс. шаг {cb[3]:6.1f} м  ({len(before)} точек)")
        print(f"  ПОСЛЕ: разброс p50 {ca[0]:6.1f} м  max {ca[1]:6.1f} м  "
              f"точность ~{ca[2]:.1f} м  макс. шаг {ca[3]:6.1f} м  ({len(after)} точек)")
        if ob is not None and oa is not None:
            delta = oa - ob
            print(f"  ОДОМЕТР: {ob:.0f} -> {oa:.0f} км  (дельта {delta:+.1f}, "
                  f"замеры ±{ob_dt:.0f}/{oa_dt:.0f} с от границы)")
        else:
            print("  ОДОМЕТР: нет данных рядом с разрывом")
        print(f"  скорость: до {a[4]}  после {b[4]} км/ч")
    return 0


if __name__ == "__main__":
    sys.exit(main())
