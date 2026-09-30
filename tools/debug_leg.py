"""Trace one leg of the real archive to find which code path lets a spike through.

Run: .venv\\Scripts\\python.exe tools\\debug_leg.py <locator.sqlite> <target_index>
"""
from __future__ import annotations

import importlib.util
import math
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "flt", ROOT / "custom_components" / "gwm_jolion" / "locator_filter.py"
)
flt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(flt)


def main() -> int:
    db = sqlite3.connect(f"file:{Path(sys.argv[1]).as_posix()}?mode=ro", uri=True)
    rows = db.execute(
        "SELECT timestamp_ms, latitude, longitude, accuracy_m, speed_kmh, speed_accuracy_kmh "
        "FROM points ORDER BY timestamp_ms"
    ).fetchall()
    db.close()
    target_index = int(sys.argv[2])

    points = [
        {"id": f"p{r[0]}", "timestamp_ms": r[0], "latitude": r[1], "longitude": r[2],
         "accuracy_m": r[3], "speed_kmh": r[4], "speed_accuracy_kmh": r[5],
         "source": "app", "time_known": True, "accuracy_known": True}
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
        displayed.extend(flt.filter_display(leg))
    victim = displayed[target_index]
    stamp = victim["timestamp_ms"]

    leg = next(leg for leg in legs if leg[0]["timestamp_ms"] <= stamp <= leg[-1]["timestamp_ms"])
    print(f"отрезок: {len(leg)} точек, {leg[0]['timestamp_ms']} .. {leg[-1]['timestamp_ms']}")
    position = next(i for i, p in enumerate(leg) if p["timestamp_ms"] == stamp)
    print(f"виновник — индекс {position} в отрезке\n")

    original_limit = flt.step_limit
    calls = {"n": 0}

    def traced_limit(previous, p, elapsed, resuming=False):
        limit = original_limit(previous, p, elapsed, resuming)
        if abs(position - leg.index(p)) <= 6 and p["timestamp_ms"] >= stamp - 8000:
            calls["n"] += 1
            step = flt.meters(previous, p)
            print(
                f"  step_limit: idx={leg.index(p):5} step={step:7.1f} limit={limit:8.1f} "
                f"{'ПРОПУЩЕНО' if step <= limit else 'отклонено'} "
                f"anchored={flt.anchored_hold(previous)} resuming={resuming} "
                f"spd_p={(p['speed_kmh'] if p['speed_kmh'] is not None else -1):6.2f}"
            )
        return limit

    original_confirmed = flt.confirmed
    traced_confirmed_calls = {"n": 0}

    def traced_confirmed(group):
        result = original_confirmed(group)
        if group and group[-1]["timestamp_ms"] >= stamp - 8000 and group[-1]["timestamp_ms"] <= stamp + 20000:
            traced_confirmed_calls["n"] += 1
            print(f"  confirmed(группа из {len(group)}) -> {result} "
                  f"idx={[leg.index(g) for g in group]}")
        return result

    flt.step_limit = traced_limit
    flt.confirmed = traced_confirmed
    flt._leg.__globals__["step_limit"] = traced_limit
    flt._leg.__globals__["confirmed"] = traced_confirmed
    out = flt._leg(leg)
    print(f"\nвызовов step_limit рядом: {calls['n']}, confirmed: {traced_confirmed_calls['n']}")
    for k in range(max(0, position - 3), min(len(out), position + 3)):
        p = out[k]
        mark = " <-- ВИНОВНИК" if k == position else ""
        print(f"  out[{k:5}] закреп={str(bool(p.get('display_filtered'))):5} "
              f"spd={(p['speed_kmh'] if p['speed_kmh'] is not None else -1):6.2f}{mark}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
