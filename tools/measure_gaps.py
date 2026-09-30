"""Break every transmission gap down by duration and resume distance.

Answers the design question for inferred parking: a long silence that resumes
at the same place means the car stood still, while a different place means the
data was simply lost and no route may be drawn across it.

Run: .venv\\Scripts\\python.exe tools\\measure_gaps.py <path-to-locator.sqlite>
"""
from __future__ import annotations

import math
from pathlib import Path
import sqlite3
import sys


def meters(a, b) -> float:
    lat1, lat2 = math.radians(a[0]), math.radians(b[0])
    dlat = lat2 - lat1
    dlon = math.radians(b[1] - a[1])
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371000 * 2 * math.asin(math.sqrt(min(1, h)))


def bucket(seconds: float) -> str:
    for limit in (30, 60, 120, 300, 600, 1200, 1800, 3600, 4 * 3600, 12 * 3600):
        if seconds <= limit:
            return f"<= {limit // 60} min" if limit < 3600 else f"<= {limit // 3600} h"
    return "> 12 h"


def main() -> int:
    path = Path(sys.argv[1])
    db = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    rows = db.execute(
        "SELECT timestamp_ms, latitude, longitude, accuracy_m, speed_kmh "
        "FROM points ORDER BY timestamp_ms"
    ).fetchall()
    db.close()

    print(f"{'разрыв':>12} {'длит.':>10} {'дист.':>9} {'скорость':>18} {'вердикт':>22}")
    print("-" * 78)
    stats: dict[str, list[int]] = {}
    for a, b in zip(rows, rows[1:]):
        dt = (b[0] - a[0]) / 1000
        if dt <= 120:
            continue
        d = meters((a[1], a[2]), (b[1], b[2]))
        before = a[4]
        after = b[4]
        verdict = "то же место" if d <= 50 else "другое место"
        print(
            f"{'':>12} {dt / 3600:9.2f} h {d:8.0f} m "
            f"{('-' if before is None else f'{before:.1f}')} -> {('-' if after is None else f'{after:.1f}'):>6} "
            f"{verdict:>22}"
        )
        key = bucket(dt)
        entry = stats.setdefault(key, [0, 0])
        entry[1] += 1
        if d <= 50:
            entry[0] += 1

    print("\nсводка по длительности разрыва:")
    for key in sorted(stats, key=lambda k: (len(k), k)):
        same, total = stats[key]
        print(f"  {key:>12}: возобновление на месте {same}/{total}")

    hours = [(b[0] - a[0]) / 3600 for a, b in zip(rows, rows[1:]) if (b[0] - a[0]) / 1000 > 600]
    if hours:
        print(f"\nразрывов длиннее 10 минут: {len(hours)}")
        for h in sorted(hours, reverse=True):
            print(f"  {h:6.2f} ч")
    return 0


if __name__ == "__main__":
    sys.exit(main())
