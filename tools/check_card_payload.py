"""Check the exact payload the trips card receives over the WebSocket.

The card only ever calls `gwm_jolion/trips` and reads `parking_spots`, so the
inferred parking has to be visible there. This exercises the real merge function
on the real archive and prints the shape the card will render.

Run: .venv\\Scripts\\python.exe tools\\check_card_payload.py <locator.sqlite> <trips.sqlite>
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "gwm_jolion"


def load(name, extra=None):
    spec = importlib.util.spec_from_file_location(name, COMPONENT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    if extra:
        spec.loader.exec_module(module, extra)
    else:
        spec.loader.exec_module(module)
    return module


def main() -> int:
    protocol = load("locator_protocol")
    flt = load("locator_filter")
    # locator.py imports HA modules, so pull the merge function out on its own.
    source = (COMPONENT / "locator.py").read_text(encoding="utf-8")
    start = source.index("def merge_inferred_parking")
    end = source.index("class HybridHistory")
    namespace = {"analyze": protocol.analyze}
    exec(compile(source[start:end], "locator.py", "exec"), namespace)
    merge = namespace["merge_inferred_parking"]

    app = sqlite3.connect(f"file:{Path(sys.argv[1]).as_posix()}?mode=ro", uri=True)
    rows = app.execute(
        "SELECT timestamp_ms, latitude, longitude, accuracy_m, speed_kmh, speed_accuracy_kmh "
        "FROM points ORDER BY timestamp_ms"
    ).fetchall()
    app.close()
    cloud = sqlite3.connect(f"file:{Path(sys.argv[2]).as_posix()}?mode=ro", uri=True)
    odometer_rows = cloud.execute(
        "SELECT ts, odo FROM points WHERE odo IS NOT NULL ORDER BY ts"
    ).fetchall()
    cloud.close()

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
    filtered = []
    for leg in legs:
        filtered.extend(flt.filter_display(leg))

    mileage = [(ts, None, None, odo) for ts, odo in odometer_rows]
    spots = merge([], filtered, mileage)
    print(f"parking_spots в ответе карточки: {len(spots)}")
    inferred = [s for s in spots if s.get("inferred")]
    print(f"из них выведенных через сон: {len(inferred)}")
    for s in spots:
        hours = (s["end"] - s["start"]) / 3600 if s.get("end") else 0
        mark = f" <- выведена ({s.get('inferred_by')})" if s.get("inferred") else ""
        print(f"  {hours:6.2f} ч  start={s['start']:.0f}  end={s.get('end')}{mark}")

    # Overlapping letters would be a visible defect.
    ordered = sorted(spots, key=lambda s: s["start"])
    clashes = [
        (a, b) for a, b in zip(ordered, ordered[1:])
        if a.get("end") is not None and b["start"] < a["end"] - 60
    ]
    print(f"\nналожений меток: {len(clashes)}")
    for a, b in clashes:
        print(f"  {a['start']:.0f}..{a['end']:.0f} и {b['start']:.0f}..{b.get('end')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
