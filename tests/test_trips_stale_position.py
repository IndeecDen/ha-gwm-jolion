"""A cached cloud position is not a trip, and it must not hide the parking under it.

Field case, 2026-11-16: the car drove 11 km in two identical loops, 09:44-10:12 and
16:11-16:28, and stood at home for the six hours between them. For those six hours
the GWM cloud kept repeating one coordinate 107 km away - 4148 identical fixes,
entered 460 s after the car parked and left 33 s before the evening loop, while the
odometer never moved. Both jumps were counted as travel and the run between them
destroyed the midday parking, so the card drew the whole day as one 230 km trip in
one colour with two parking markers.

Run: .venv\\Scripts\\python.exe -m pytest -q tests/test_trips_stale_position.py
"""
import importlib.util
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "gwm_jolion"
spec = importlib.util.spec_from_file_location("trip_history", ROOT / "trips.py")
trips = importlib.util.module_from_spec(spec)
spec.loader.exec_module(trips)

HOME = (52.6189, 39.6089)
FAR = (51.6591, 39.2537)
ZONE = "Europe/Moscow"
TZ = ZoneInfo(ZONE)
DAY = "2026-11-16"
BASE = datetime(2026, 11, 16, tzinfo=TZ).timestamp()
H = 3600


def row(stamp, place, odo=None):
    return (stamp, place[0], place[1], odo)


def parked(start, count, step, place, odo=None):
    return [row(start + index * step, place, odo) for index in range(count)]


def loop(start, odo_from, odo_to, reach=0.025, minutes=20):
    """Out and back along a meridian: the shape of both identical drives."""
    rows, half = [], minutes // 2
    for index in range(minutes + 1):
        share = index / half if index <= half else 2 - index / half
        odo = odo_from + (odo_to - odo_from) * index / minutes
        rows.append(row(start + index * 60, (HOME[0] + reach * share, HOME[1]), round(odo, 2)))
    return rows


def field_day():
    """2026-11-16 as it was recorded: two loops, six hours of a cached position."""
    island_start = BASE + 10 * H + 19 * 60 + 47
    island_end = BASE + 16 * H + 11 * 60
    return [*parked(BASE, 1160, 30, HOME, 0.0),
            *loop(BASE + 9 * H + 40 * 60, 0.0, 5.5),
            *parked(BASE + 10 * H + 30, 19, 60, HOME, 5.5),
            *parked(island_start, int((island_end - island_start) // 30), 30, FAR, 5.5),
            *parked(BASE + 16 * H + 11 * 60 + 30, 17, 60, HOME, 5.5),
            *loop(BASE + 16 * H + 28 * 60, 5.5, 11.0),
            *parked(BASE + 16 * H + 49 * 60, 200, 60, HOME, 11.0)]


def test_the_cached_run_is_dropped_not_driven():
    """One frozen coordinate is not 4148 observations of a car standing in Voronezh."""
    rows = field_day()
    cached = {index for index, item in enumerate(rows)
              if abs(item[1] - FAR[0]) < 1e-6 and abs(item[2] - FAR[1]) < 1e-6}
    assert len(cached) > 700
    assert trips.stale_run_indices(rows) == cached


def test_the_day_is_two_loops_not_one_230_km_trip():
    result = trips.summarize(field_day(), DAY, DAY, ZONE)
    windows = result["trips"]
    assert len(windows) == 2
    assert all(window["km"] < 20 for window in windows)
    assert 9 <= sum(window["km"] for window in windows) <= 13
    assert result["km"] == 11.0


def test_the_cached_coordinate_is_never_drawn():
    rows = field_day()
    result = trips.summarize(rows, DAY, DAY, ZONE)
    points = [point for segment in result["segments"] for point in segment]
    assert not [point for point in points
                if abs(point[0] - FAR[0]) < 1e-3 and abs(point[1] - FAR[1]) < 1e-3]
    assert result["samples"] < len(rows)


def test_the_parking_under_the_cached_run_keeps_its_hours():
    """The midday stop has to span the hole: it is what separates the two colours."""
    result = trips.summarize(field_day(), DAY, DAY, ZONE)
    stops = result["parking_spots"]
    assert len(stops) == 3
    middle = [stop for stop in stops
              if stop["start"] < BASE + 11 * H and stop["observed_until"] > BASE + 16 * H]
    assert len(middle) == 1
    stop = middle[0]
    assert stop["start"] <= BASE + 10 * H + 60
    assert stop["end"] >= BASE + 16 * H + 20 * 60
    assert stop["duration"] >= 5 * H
    assert stop["interruptions"]


def test_without_an_odometer_missing_time_stays_missing():
    """A position alone cannot tell a car that was towed from a fix that was cached."""
    home = parked(BASE + 10 * H, 19, 60, HOME)
    back = parked(BASE + 16 * H, 17, 60, HOME)
    assert len(trips.parking_spots(home + back, minimum_seconds=60)) == 2

    proven = parked(BASE + 10 * H, 19, 60, HOME, 5.5) + parked(BASE + 16 * H, 17, 60, HOME, 5.5)
    stops = trips.parking_spots(proven, minimum_seconds=60)
    assert len(stops) == 1
    assert stops[0]["interruptions"] == [[home[-1][0], back[0][0]]]


def test_a_real_parking_far_from_home_survives():
    """A place the car can reach by driving is a place, not a cached coordinate."""
    away = (HOME[0] + 0.05, HOME[1])
    rows = parked(BASE, 10, 60, HOME)
    rows += [row(BASE + 600 + index * 60, (HOME[0] + 0.0025 * index, HOME[1])) for index in range(1, 21)]
    rows += parked(BASE + 1860, 40, 60, away)
    rows += [row(BASE + 4320 + index * 60, (away[0] - 0.0025 * index, HOME[1])) for index in range(1, 21)]
    assert trips.stale_run_indices(rows) == set()


def test_the_playback_does_not_replay_the_cached_run():
    rows = [(item[0], item[1], item[2], None) for item in field_day()]
    result = trips.with_archive(rows, ([], []), DAY, DAY, ZONE)
    played = [point for point in result["playback"]
              if abs(point["latitude"] - FAR[0]) < 1e-3 and abs(point["longitude"] - FAR[1]) < 1e-3]
    assert not played


def test_a_driven_hole_becomes_a_grey_link():
    """The track the receiver missed while the odometer was counting belongs on the map."""
    rows = [*parked(BASE, 10, 60, HOME, 0.0),
            row(BASE + 900, FAR, 8.5), row(BASE + 960, FAR, 8.6), row(BASE + 1020, FAR, 8.7)]
    result = trips.summarize(rows, DAY, DAY, ZONE)
    assert len(result["gaps"]) == 1
    link = result["gap_links"][0]
    assert link["from"] == [HOME[0], HOME[1]] and link["to"] == [FAR[0], FAR[1]]
    assert link["seconds"] == 360
    assert link["odometer_km"] == 8.5
    assert link["distance_km"] > 100


def test_a_hole_without_an_odometer_gets_no_link():
    """No odometer reading means no proof of travel, and the map draws nothing."""
    rows = [*parked(BASE, 10, 60, HOME),
            row(BASE + 900, FAR), row(BASE + 960, FAR)]
    result = trips.summarize(rows, DAY, DAY, ZONE)
    assert len(result["gaps"]) == 1
    assert result["gap_links"][0]["odometer_km"] is None
