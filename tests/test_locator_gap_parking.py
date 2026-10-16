"""Parking inferred across a transmission gap.

A parked car sleeps: no T-Box fixes and no phone upload. The odometer is the
only signal that tells sleeping apart from moving, so it decides first and the
position is only a fallback.

Run: .venv\\Scripts\\python.exe -m pytest -q tests/test_locator_gap_parking.py
"""
import importlib.util
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "gwm_jolion"
spec = importlib.util.spec_from_file_location("gap_protocol", ROOT / "locator_protocol.py")
protocol = importlib.util.module_from_spec(spec)
spec.loader.exec_module(protocol)

analyze = protocol.analyze
BASE = 1_700_000_000_000


def point(offset_s, x=0.0, speed=0.0, accuracy=5.0, **extra):
    return {
        "timestamp_ms": BASE + int(offset_s * 1000),
        "latitude": 55.0 + x / 111195,
        "longitude": 37.0,
        "accuracy_m": accuracy,
        "speed_kmh": speed,
        **extra,
    }


def parked_run(start_s, count, x=0.0, step=1.0):
    return [point(start_s + i * step, x, speed=0.0) for i in range(count)]


def odo(pairs):
    return {BASE + int(t * 1000): v for t, v in pairs}


def test_odometer_proves_parking_across_a_sleep_gap():
    before = parked_run(0, 400)
    after = parked_run(400 + 8 * 3600, 400)
    result = analyze(before + after, odo([(390, 78502.0), (400 + 8 * 3600 + 10, 78502.0)]))
    stops = result["stops"]
    assert len(stops) == 1, stops
    assert stops[0]["inferred"] is True
    assert stops[0]["inferred_by"] == "odometer"
    assert stops[0]["duration_s"] > 8 * 3600
    # The long silence is parking, so it is one merged stop, not three letters.
    assert stops[0]["start_ms"] == BASE
    assert stops[0]["end_ms"] == BASE + int((400 + 8 * 3600 + 399) * 1000)


def test_odometer_shows_the_car_moved_so_no_parking_is_invented():
    before = parked_run(0, 400)
    after = parked_run(400 + 8 * 3600, 400, x=3000)
    result = analyze(before + after, odo([(390, 78502.0), (400 + 8 * 3600 + 10, 78506.0)]))
    assert not [s for s in result["stops"] if s.get("inferred")]


def test_a_towed_car_is_not_reported_as_parked_even_at_the_same_place():
    """Same coordinates, but the wheels turned: the odometer wins over GPS."""
    before = parked_run(0, 400)
    after = parked_run(400 + 8 * 3600, 400)
    result = analyze(before + after, odo([(390, 78502.0), (400 + 8 * 3600 + 10, 78503.5)]))
    assert not [s for s in result["stops"] if s.get("inferred")]


def test_position_fallback_only_when_the_odometer_is_missing():
    before = parked_run(0, 400)
    after = parked_run(400 + 8 * 3600, 400, x=90)
    assert analyze(before + after)[ "stops"] == analyze(before + after)["stops"]
    inferred = [s for s in analyze(before + after)["stops"] if s.get("inferred")]
    assert len(inferred) == 1 and inferred[0]["inferred_by"] == "position"
    # Far away and no odometer: stay a gap rather than guessing.
    far = parked_run(400 + 8 * 3600, 400, x=3000)
    assert not [s for s in analyze(before + far)["stops"] if s.get("inferred")]


def test_short_gaps_never_become_parking():
    before = parked_run(0, 400)
    after = parked_run(400 + 120, 400)
    result = analyze(before + after, odo([(390, 78502.0), (530, 78502.0)]))
    assert not [s for s in result["stops"] if s.get("inferred")]


def test_a_real_track_keeps_its_gap_and_stays_measurable():
    """Driving, then a long outage, then driving elsewhere: no line across it."""
    drive = [point(i * 1.0, x=i * 12, speed=50, accuracy=4) for i in range(600)]
    resume = 600 + 4 * 3600
    drive2 = [point(resume + i * 1.0, x=7200 + i * 12, speed=50, accuracy=4) for i in range(600)]
    result = analyze(drive + drive2, odo([(590, 100.0), (resume + 10, 180.0)]))
    assert not [s for s in result["stops"] if s.get("inferred")]
    # Two separate segments: the outage is never bridged.
    assert len(result["segments"]) == 2


def test_same_app_gap_at_same_place_exposes_parking_without_odometer():
    before = point(0, x=0, speed=0, accuracy=4, source="app")
    before["display_break"] = True
    after = point(3600, x=0, speed=0, accuracy=4, source="app")
    after["display_break"] = True
    result = analyze([before, after])
    assert len(result["stops"]) == 1
    stop = result["stops"][0]
    assert stop["inferred"] is True and stop["inferred_by"] == "position"
    assert stop["duration_s"] == 3600


def test_source_switch_still_does_not_infer_parking_from_position():
    before = point(0, x=0, speed=0, accuracy=4, source="app")
    before["display_break"] = True
    after = point(3600, x=0, speed=0, accuracy=4, source="cloud")
    after["display_break"] = True
    result = analyze([before, after])
    assert not result["stops"]


def test_inferred_stop_carries_the_flag_the_card_needs():
    before = parked_run(0, 400)
    after = parked_run(400 + 8 * 3600, 400)
    result = analyze(before + after, odo([(390, 78502.0), (400 + 8 * 3600 + 10, 78502.0)]))
    stop = result["stops"][0]
    assert set(stop) >= {"start_ms", "end_ms", "latitude", "longitude", "duration_s", "inferred"}


def test_merge_puts_inferred_parking_into_the_list_the_card_reads():
    """The card only calls gwm_jolion/trips and reads parking_spots."""
    source = (Path(__file__).resolve().parents[1] / "custom_components" / "gwm_jolion" / "locator.py")
    text = source.read_text(encoding="utf-8")
    start = text.index("def merge_inferred_parking")
    end = text.index("class HybridHistory")
    namespace = {"analyze": analyze}
    exec(compile(text[start:end], "locator.py", "exec"), namespace)
    merge = namespace["merge_inferred_parking"]

    before = parked_run(0, 400)
    after = parked_run(400 + 8 * 3600, 400)
    points = before + after
    # Mileage arrives in seconds on the same epoch, as summarize() consumes it.
    mileage = [(before[-1]["timestamp_ms"] / 1000, None, None, 78502.0),
               (after[0]["timestamp_ms"] / 1000 + 10, None, None, 78502.0)]
    spots = merge([], points, mileage)
    assert len(spots) == 1
    spot = spots[0]
    assert spot["inferred"] is True
    assert spot["inferred_by"] == "odometer", "миллисекунды и секунды перепутаны"
    assert spot["end"] - spot["start"] > 8 * 3600
    # The silence merges with the parking observed before and after it.
    assert spot["start"] <= before[-1]["timestamp_ms"] / 1000
    assert spot["end"] >= after[-1]["timestamp_ms"] / 1000


def test_mixed_cloud_and_app_points_do_not_break_the_history_query():
    """Cloud fixes have accuracy_m = None; comparing that with a number aborted
    the whole WebSocket query and the card showed "история недоступна"."""
    source = (Path(__file__).resolve().parents[1] / "custom_components" / "gwm_jolion" / "locator.py")
    text = source.read_text(encoding="utf-8")
    start = text.index("def merge_inferred_parking")
    end = text.index("class HybridHistory")
    namespace = {"analyze": analyze}
    exec(compile(text[start:end], "locator.py", "exec"), namespace)
    merge = namespace["merge_inferred_parking"]

    def cloud(offset_s, x=0.0):
        return {"id": f"cloud-{offset_s}", "timestamp_ms": BASE + int(offset_s * 1000),
                "latitude": 55.0 + x / 111195, "longitude": 37.0,
                "accuracy_m": None, "speed_kmh": None, "bearing": None, "altitude_m": None,
                "source": "cloud", "time_known": False, "accuracy_known": False}

    before = parked_run(0, 400)
    between = [cloud(700 + i, x=5) for i in range(120)]
    after = parked_run(400 + 8 * 3600, 400)
    points = [*before, *between, *after]
    mileage = [(before[-1]["timestamp_ms"] / 1000, None, None, 78502.0),
               (after[0]["timestamp_ms"] / 1000 + 10, None, None, 78502.0)]

    spots = merge([], points, mileage)          # must not raise
    assert any(s.get("inferred") for s in spots)
    # A fix with unknown accuracy must not confirm a stop of its own either.
    assert all(isinstance(s["start_ms"] if "start_ms" in s else s["start"], (int, float)) for s in spots)


def test_analyze_survives_points_without_measured_accuracy():
    points = [point(i, x=i * 0.5, speed=0, accuracy=None) for i in range(200)]
    result = analyze(points)                    # must not raise
    assert "segments" in result and "stops" in result


def test_merge_never_duplicates_a_parking_the_observations_already_found():
    source = (Path(__file__).resolve().parents[1] / "custom_components" / "gwm_jolion" / "locator.py")
    text = source.read_text(encoding="utf-8")
    start = text.index("def merge_inferred_parking")
    end = text.index("class HybridHistory")
    namespace = {"analyze": analyze}
    exec(compile(text[start:end], "locator.py", "exec"), namespace)
    merge = namespace["merge_inferred_parking"]

    before = parked_run(0, 400)
    after = parked_run(400 + 8 * 3600, 400)
    points = before + after
    mileage = [(before[-1]["timestamp_ms"] / 1000, None, None, 78502.0),
               (after[0]["timestamp_ms"] / 1000 + 10, None, None, 78502.0)]
    # One observed spot already covering the whole silence.
    observed = [{"latitude": before[-1]["latitude"], "longitude": before[-1]["longitude"],
                 "start": before[0]["timestamp_ms"] / 1000, "end": after[-1]["timestamp_ms"] / 1000,
                 "observed_until": after[-1]["timestamp_ms"] / 1000, "duration": 8 * 3600 + 400}]
    spots = merge(observed, points, mileage)
    assert len(spots) == 1
    assert "inferred" not in spots[0]
