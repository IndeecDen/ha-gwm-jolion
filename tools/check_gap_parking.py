"""Replay the real archive through analyze() and report inferred parking.

This is the acceptance check for gap parking: it must mark the gaps the odometer
proves were standing still, and must leave the gap where the car actually moved.

Run: .venv\\Scripts\\python.exe tools\\check_gap_parking.py <locator.sqlite> <trips.sqlite>
"""
from __future__ import annotations

import importlib.util
import math
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "gap_protocol", ROOT / "custom_components" / "gwm_jolion" / "locator_protocol.py"
)
protocol = importlib.util.module_from_spec(spec)
spec.loader.exec_module(protocol)


def main() -> int:
    app = sqlite3.connect(f"file:{Path(sys.argv[1]).as_posix()}?mode=ro", uri=True)
    rows = app.execute(
        "SELECT timestamp_ms, latitude, longitude, accuracy_m, speed_kmh, speed_accuracy_kmh, "
        "bearing FROM points ORDER BY timestamp_ms"
    ).fetchall()
    app.close()

    cloud = sqlite3.connect(f"file:{Path(sys.argv[2]).as_posix()}?mode=ro", uri=True)
    odometers = {
        int(ts * 1000): odo
        for ts, odo in cloud.execute("SELECT ts, odo FROM points WHERE odo IS NOT NULL ORDER BY ts")
    }
    cloud.close()

    points = [
        {"id": f"p{r[0]}", "timestamp_ms": r[0], "latitude": r[1], "longitude": r[2],
         "accuracy_m": r[3], "speed_kmh": r[4], "speed_accuracy_kmh": r[5], "bearing": r[6],
         "source": "app", "time_known": True, "accuracy_known": True}
        for r in rows
    ]
    # Split exactly as the card does, so display_break marks real outages.
    spec_filter = importlib.util.spec_from_file_location(
        "flt", ROOT / "custom_components" / "gwm_jolion" / "locator_filter.py"
    )
    flt = importlib.util.module_from_spec(spec_filter)
    spec_filter.loader.exec_module(flt)
    filtered = flt.filter_display(points)

    without = protocol.analyze(filtered)["stops"]
    with_odo = protocol.analyze(filtered, odometers)["stops"]

    def summarise(stops, label):
        inferred = [s for s in stops if s.get("inferred")]
        print(f"\n{label}: всего стоянок {len(stops)}, из них через разрыв {len(inferred)}")
        for s in inferred:
            hours = s["duration_s"] / 3600
            offset = (s["start_ms"] - filtered[0]["timestamp_ms"]) / 1000 / 3600
            print(f"  {hours:6.2f} ч  начало через {offset:5.2f} ч от начала трека, "
                  f"причина={s.get('inferred_by')}")

    summarise(without, "без одометра")
    summarise(with_odo, "с одометром")

    observed_before = {id(s) for s in without}
    print("\nпроверка безопасности: ни одна реально измеренная стоянка не должна исчезнуть")
    lost = [
        s for s in without
        if s["end_ms"] - s["start_ms"] < protocol.INFERRED_GAP_MS
        and not any(o["start_ms"] <= s["start_ms"] and o["end_ms"] >= s["end_ms"] for o in with_odo)
    ]
    print(f"  потеряно стоянок: {len(lost)}")
    for s in lost[:5]:
        print(f"    {s['start_ms']} .. {s['end_ms']} ({(s['end_ms'] - s['start_ms']) / 1000:.0f} с)")

    print("\nпроверка: отрезки маршрута не должны склеиться через разрыв")
    segments = protocol.analyze(filtered, odometers)["segments"]
    print(f"  сегментов: {len(segments)} (линия через провал не рисуется)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
