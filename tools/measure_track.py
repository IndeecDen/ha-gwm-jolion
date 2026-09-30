"""Measure real GPS behaviour from the vehicle archive.

Prints distributions only, never coordinates. Used to choose filter thresholds
from evidence instead of guessing.

Run: .venv\\Scripts\\python.exe tools\\measure_track.py <path-to-locator.sqlite>
"""
from __future__ import annotations

from collections import Counter
import math
from pathlib import Path
import sqlite3
import statistics
import sys


def meters(a_lat, a_lon, b_lat, b_lon) -> float:
    lat1, lat2 = math.radians(a_lat), math.radians(b_lat)
    dlat = lat2 - lat1
    dlon = math.radians(b_lon - a_lon)
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371000 * 2 * math.asin(math.sqrt(min(1, h)))


def quantile(values, q):
    if not values:
        return None
    ordered = sorted(values)
    k = (len(ordered) - 1) * q
    lo, hi = math.floor(k), math.ceil(k)
    if lo == hi:
        return ordered[int(k)]
    return ordered[lo] * (hi - k) + ordered[hi] * (k - lo)


def main() -> int:
    path = Path(sys.argv[1])
    db = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
    print(f"integrity: {integrity}")
    count = db.execute("SELECT COUNT(*) FROM points").fetchone()[0]
    first = db.execute("SELECT MIN(timestamp_ms), MAX(timestamp_ms) FROM points").fetchone()
    span_days = (first[1] - first[0]) / 86400000 if first[0] and first[1] else 0
    print(f"points: {count}   span: {span_days:.2f} days")

    rows = db.execute(
        "SELECT timestamp_ms, latitude, longitude, accuracy_m, speed_kmh, "
        "speed_accuracy_kmh, bearing, altitude_m FROM points ORDER BY timestamp_ms"
    ).fetchall()
    if not rows:
        print("empty archive")
        return 0

    print("\n--- интервалы между точками (с) ---")
    gaps = sorted((b["timestamp_ms"] - a["timestamp_ms"]) / 1000 for a, b in zip(rows, rows[1:]))
    for label, q in (("p50", 0.5), ("p90", 0.9), ("p99", 0.99), ("max", 1.0)):
        print(f"  {label:4} {quantile(gaps, q):10.1f}")
    buckets = Counter()
    for g in gaps:
        for limit in (5, 15, 30, 60, 120, 300, 600, 1800, 3600, 14400):
            if g <= limit:
                buckets[limit] += 1
                break
        else:
            buckets[float("inf")] += 1
    print("  распределение:", {k: v for k, v in sorted(buckets.items(), key=lambda kv: str(kv[0]))})

    print("\n--- точность, м ---")
    acc = [r["accuracy_m"] for r in rows if r["accuracy_m"] is not None]
    for label, q in (("p05", 0.05), ("p50", 0.5), ("p90", 0.9), ("p99", 0.99)):
        print(f"  {label:4} {quantile(acc, q):8.1f}")

    print("\n--- скорость, км/ч ---")
    spd = [r["speed_kmh"] for r in rows if r["speed_kmh"] is not None]
    print(f"  точек со скоростью: {len(spd)} из {len(rows)}")
    for label, q in (("p10", 0.1), ("p50", 0.5), ("p90", 0.9)):
        print(f"  {label:4} {quantile(spd, q):8.2f}")
    slow = [s for s in spd if s <= 3]
    print(f"  доля «стоит» (speed<=3): {len(slow)/len(spd):.1%}" if spd else "")

    print("\n--- jitter while stopped (speed <=3, interval <=5 s) ---")
    for acc_max in (5, 10, 20, 35, 50):
        spread = []
        group = []
        for a, b in zip(rows, rows[1:]):
            dt = (b["timestamp_ms"] - a["timestamp_ms"]) / 1000
            near_stop = (
                a["speed_kmh"] is not None and b["speed_kmh"] is not None
                and max(a["speed_kmh"], b["speed_kmh"]) <= 3
                and a["accuracy_m"] <= acc_max and b["accuracy_m"] <= acc_max
                and 0 < dt <= 5
            )
            if not near_stop:
                if len(group) >= 5:
                    spread.append(group)
                group = []
                continue
            group.append(b)
        if len(group) >= 5:
            spread.append(group)
        if not spread:
            continue
        radii = []
        for group in spread:
            lat0 = statistics.fmean(p["latitude"] for p in group)
            lon0 = statistics.fmean(p["longitude"] for p in group)
            radii.append(max(meters(lat0, lon0, p["latitude"], p["longitude"]) for p in group))
        print(
            f"  accuracy<={acc_max:2} м: групп {len(spread):5}, "
            f"радиус p50 {quantile(radii,0.5):5.1f} м, p90 {quantile(radii,0.9):6.1f} м, "
            f"max {max(radii):7.1f} м"
        )

    print("\n--- «провалы» >5 мин: возобновление на том же месте? ---")
    same = different = 0
    resume_radii = []
    for a, b in zip(rows, rows[1:]):
        dt = (b["timestamp_ms"] - a["timestamp_ms"]) / 1000
        if dt <= 300:
            continue
        d = meters(a["latitude"], a["longitude"], b["latitude"], b["longitude"])
        resume_radii.append(d)
        if d <= 50:
            same += 1
        else:
            different += 1
    print(f"  разрывов >5 мин: {len(resume_radii)}   возобновление рядом (<=50 м): {same}   в другом месте: {different}")
    if resume_radii:
        print(f"  расстояние возобновления: p10 {quantile(resume_radii,0.1):.0f} м, "
              f"p50 {quantile(resume_radii,0.5):.0f} м, p90 {quantile(resume_radii,0.9):.0f} м")

    print("\n--- доля точек с bearing/altitude ---")
    print(f"  bearing: {sum(1 for r in rows if r['bearing'] is not None)}/{len(rows)}")
    print(f"  altitude: {sum(1 for r in rows if r['altitude_m'] is not None)}/{len(rows)}")
    db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
