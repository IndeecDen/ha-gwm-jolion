"""A parked car is one parking, not one marker per data gap.

Field test, 2026-09-26/27: the phone sat in the car for a day and a half. Its
reported speed jumped to 7-27 km/h while standing still, its accuracy climbed from
2 m past the 50 m the old test trusted, its upload stream punched holes of up to
124 s, and the T-Box kept inserting fixes that carry no speed and no measured
accuracy. Each of those used to end the stop, so one parked night became twelve
markers - which is why the letters on the map did not follow the trip and why a
marker appeared next to the track instead of at it.

Position is the only evidence that proves the car left. Run: .venv\\Scripts\\python.exe -m pytest -q tests/test_parking_continuity.py
"""
import importlib.util
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "gwm_jolion"
spec = importlib.util.spec_from_file_location("parking_protocol", ROOT / "locator_protocol.py")
protocol = importlib.util.module_from_spec(spec)
spec.loader.exec_module(protocol)

analyze = protocol.analyze
BASE = 1_700_000_000_000
LAT, LON = 55.0, 37.0


def app(offset_s, dx=0.0, speed=0.0, accuracy=5.0):
    """A phone fix: known time, known accuracy, a reported speed."""
    return {
        "id": f"app-{offset_s}-{dx}", "timestamp_ms": BASE + int(offset_s * 1000),
        "latitude": LAT + dx / 111195, "longitude": LON,
        "accuracy_m": accuracy, "speed_kmh": speed, "bearing": None,
        "altitude_m": None, "source": "app", "time_known": True,
        "accuracy_known": True,
    }


def cloud(offset_s, dx=0.0):
    """A T-Box fix: no measured accuracy and no speed at all."""
    return {
        "id": f"cloud-{offset_s}", "timestamp_ms": BASE + int(offset_s * 1000),
        "latitude": LAT + dx / 111195, "longitude": LON,
        "accuracy_m": None, "speed_kmh": None, "bearing": None,
        "altitude_m": None, "source": "cloud", "time_known": False,
        "accuracy_known": False,
    }


def merged(*groups):
    points = []
    for group in groups:
        points.extend(group)
    return sorted(points, key=lambda p: p["timestamp_ms"])


def test_noisy_speed_does_not_end_a_long_parking():
    """A standing car reporting 20 km/h is a bad reading, not a departure."""
    points = merged([app(t, speed=(18 if 400 <= t < 410 else 0)) for t in range(0, 1800, 5)])
    assert len(analyze(points)["stops"]) == 1


def test_degrading_accuracy_does_not_end_a_long_parking():
    """Accuracy climbing past 50 m while stationary used to cut the stop in two."""
    points = merged([app(t, accuracy=min(80, 3 + t / 20)) for t in range(0, 1800, 5)])
    assert len(analyze(points)["stops"]) == 1


def test_upload_holes_do_not_split_a_parking():
    """The field test lost the phone stream for 124 s at a time while parked."""
    points = merged(
        [app(t) for t in range(0, 600, 5)],
        [app(t) for t in range(724, 1800, 5)],
    )
    assert len(analyze(points)["stops"]) == 1


def test_cloud_fixes_neither_confirm_nor_deny_a_parking():
    """No accuracy and no speed means nothing to decide with."""
    points = merged([app(t) for t in range(0, 1800, 5)], [cloud(t) for t in range(600, 1200, 10)])
    assert len(analyze(points)["stops"]) == 1


def test_one_parked_night_stays_one_marker():
    """The reported case: all four symptoms at once, over more than a day."""
    points = merged(
        [app(t, accuracy=min(80, 3 + (t % 400) / 15), speed=(12 if t % 211 == 0 else 0))
         for t in range(0, 90000, 5)],
        [cloud(t) for t in range(600, 90000, 30)],
    )
    assert len(analyze(points)["stops"]) == 1


def test_leaving_still_ends_the_parking():
    """Park, drive away, park again: two parkings, not one and not none."""
    home = [app(t) for t in range(0, 1800, 5)]
    # 50 km/h: the car covers 70 m between fixes, far past any radius.
    drive = [app(t, dx=(t - 1800) * 14, speed=50) for t in range(1800, 2800, 5)]
    second = [app(t, dx=14000, speed=0) for t in range(2800, 4600, 5)]
    stops = analyze(merged(home, drive, second))["stops"]
    assert len(stops) == 2
    # The parking may absorb the first stretch of the departure: leaving is proven
    # by distance, so a car that sets off does not end its stop on the same second.
    assert stops[0]["end_ms"] <= BASE + 2400 * 1000


def test_the_marker_sits_on_the_parking_not_on_its_first_fix():
    """The marker used to be the first fix, which drifted 300 m on its own."""
    drifting = [app(t, dx=(t / 40) if t < 900 else 900 / 40) for t in range(0, 1800, 5)]
    stop = analyze(merged(drifting))["stops"][0]
    expected = sum(p["latitude"] for p in drifting) / len(drifting)
    assert abs(stop["latitude"] - expected) < 1e-6
