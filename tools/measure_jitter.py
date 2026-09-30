"""Check whether the display filter actually removes track backtracking.

Loads the real app archive, runs filter_display, and compares the raw track with
the displayed one: how many steps reverse direction (the "откаты" the driver
sees), how far the filter moved points, and how long the anchors are held.

Run: .venv\\Scripts\\python.exe tools\\measure_jitter.py <path-to-locator.sqlite>
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


def steps(points):
    out = []
    for a, b in zip(points, points[1:]):
        dt = (b["timestamp_ms"] - a["timestamp_ms"]) / 1000
        if dt <= 0 or dt > 120:
            out.append(None)
            continue
        out.append(((b["longitude"] - a["longitude"]), (b["latitude"] - a["latitude"])))
    return out


def reversals(vectors, min_step_deg=0.00002):
    """Count direction reversals between consecutive non-trivial steps."""
    kept = [v for v in vectors if v is not None and math.hypot(*v) > min_step_deg]
    count = 0
    for a, b in zip(kept, kept[1:]):
        if a[0] * b[0] + a[1] * b[1] < 0:
            count += 1
    return count, len(kept)


def main() -> int:
    path = Path(sys.argv[1])
    db = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    rows = db.execute(
        "SELECT timestamp_ms, latitude, longitude, accuracy_m, speed_kmh, speed_accuracy_kmh "
        "FROM points ORDER BY timestamp_ms"
    ).fetchall()
    db.close()

    points = [
        {
            "timestamp_ms": r[0], "latitude": r[1], "longitude": r[2],
            "accuracy_m": r[3], "speed_kmh": r[4], "speed_accuracy_kmh": r[5],
            "source": "app", "id": f"p{r[0]}",
        }
        for r in rows
    ]
    # filter_display works on one leg; run it per contiguous leg as HA does.
    legs: list[list[dict]] = []
    current: list[dict] = []
    for p in points:
        if current and p["timestamp_ms"] - current[-1]["timestamp_ms"] > 30000:
            legs.append(current)
            current = []
        current.append(p)
    if current:
        legs.append(current)

    displayed: list[dict] = []
    for leg in legs:
        displayed.extend(filter_display(leg))

    print(f"исходных точек: {len(points)}  после фильтра: {len(displayed)}  (ног: {len(legs)})")

    moved = sum(
        1
        for a, b in zip(points, displayed)
        if a["latitude"] != b["latitude"] or a["longitude"] != b["longitude"]
    )
    print(f"фильтр сдвинул/закрепил точек: {moved} ({moved / len(points):.1%})")

    raw_rev, raw_steps = reversals(steps(points))
    out_rev, out_steps = reversals(steps(displayed))
    print(f"\nоткаты (смена направления):")
    print(f"  до фильтра:  {raw_rev} из {raw_steps} значимых шагов ({raw_rev / max(raw_steps,1):.1%})")
    print(f"  после:       {out_rev} из {out_steps} ({out_rev / max(out_steps,1):.1%})")

    longest = 0
    hold = 0
    prev_pos = None
    for p in displayed:
        if prev_pos is not None and p["latitude"] == prev_pos[0] and p["longitude"] == prev_pos[1]:
            hold += 1
            longest = max(longest, hold)
        else:
            hold = 0
        prev_pos = (p["latitude"], p["longitude"])
    print(f"\nнепрерывное удержание якоря: максимум {longest} точек (~{longest} с при 1 Гц)")

    # Long anchors while the engine idles at a light are fine; a 1 Hz car that is
    # genuinely creeping should not be pinned, so report pinned time share.
    pinned_time = longest
    total_time = (points[-1]["timestamp_ms"] - points[0]["timestamp_ms"]) / 1000
    print(f"доля времени в закреплении: {pinned_time / total_time:.1%} от {total_time / 3600:.1f} ч")

    steps_out = [meters((a["latitude"], a["longitude"]), (b["latitude"], b["longitude"]))
                 for a, b in zip(displayed, displayed[1:])
                 if 0 < (b["timestamp_ms"] - a["timestamp_ms"]) / 1000 <= 5]
    if steps_out:
        steps_out.sort()
        print(f"\nдлина шага после фильтра, м: p50 {steps_out[len(steps_out)//2]:.1f}, "
              f"p90 {steps_out[int(len(steps_out)*0.9)]:.1f}, max {steps_out[-1]:.1f}")

    # Split by regime: beading only matters while the car is actually moving.
    print("\n--- по режимам движения (только нарисованные шаги, без разрывов) ---")
    for label, low, high in (
        ("стоянка/стоп  0-3 км/ч", 0, 3),
        ("медленно     3-20 км/ч", 3, 20),
        ("средне     20-60 км/ч", 20, 60),
        ("быстро    >60 км/ч", 60, 1e9),
    ):
        regime_steps, regime_turns, regime_pairs = [], 0, 0
        vectors = []
        for a, b in zip(displayed, displayed[1:]):
            dt = (b["timestamp_ms"] - a["timestamp_ms"]) / 1000
            if not 0 < dt <= 10 or a.get("display_break") or b.get("display_break"):
                vectors.append(None)
                continue
            speed = b.get("speed_kmh") or 0
            if not low <= speed <= high:
                vectors.append(None)
                continue
            if a.get("display_filtered") or b.get("display_filtered"):
                vectors.append(None)
                continue
            step = meters((a["latitude"], a["longitude"]), (b["latitude"], b["longitude"]))
            regime_steps.append(step)
            regime_pairs += 1
            vectors.append((b["longitude"] - a["longitude"], b["latitude"] - a["latitude"], step))
        kept = [v for v in vectors if v is not None]
        for prev, cur in zip(kept, kept[1:]):
            if prev[2] <= 0.5 or cur[2] <= 0.5:
                continue
            if prev[0] * cur[0] + prev[1] * cur[1] < 0:
                regime_turns += 1
        if not regime_steps:
            print(f"  {label}: нет данных")
            continue
        regime_steps.sort()
        p50 = regime_steps[len(regime_steps) // 2]
        p90 = regime_steps[int(len(regime_steps) * 0.9)]
        turn_rate = regime_turns / max(regime_pairs - 1, 1)
        print(f"  {label}: пар {regime_pairs:5}  шаг p50 {p50:5.2f} м  p90 {p90:6.2f} м  "
              f"смена направления {turn_rate:5.1%}")
    # Is the reported speed trustworthy at a standstill? The fix must not touch
    # measured slow movement, so the trigger has to be unreliable speed.
    print("\n--- надёжность скорости в режиме 0-3 км/ч (нарисованные шаги) ---")
    with_error = without = unreliable = 0
    errors = []
    for a, b in zip(displayed, displayed[1:]):
        dt = (b["timestamp_ms"] - a["timestamp_ms"]) / 1000
        if not 0 < dt <= 10 or a.get("display_break") or b.get("display_break"):
            continue
        if (b.get("speed_kmh") or 0) > 3 or a.get("display_filtered") or b.get("display_filtered"):
            continue
        error = b.get("speed_accuracy_kmh")
        if error is None:
            without += 1
        else:
            with_error += 1
            errors.append(error)
            if not module.moving_speed(b):
                unreliable += 1
    print(f"  пар с заявленной погрешностью скорости: {with_error}")
    print(f"  пар без погрешности (считается надёжной):  {without}")
    if errors:
        errors.sort()
        print(f"  погрешность скорости, км/ч: p50 {errors[len(errors)//2]:.2f}, "
              f"p90 {errors[int(len(errors)*0.9)]:.2f}")
        print(f"  из них недостоверных (скорость не подтверждена): {unreliable}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
