"""Display-filter regressions using synthetic coordinates only."""
import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "gwm_jolion"
spec = importlib.util.spec_from_file_location("resilient_display_filter", ROOT / "locator_filter.py")
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def point(timestamp_ms, north_m, speed=2.16):
    return {
        "timestamp_ms": timestamp_ms,
        "latitude": 55 + north_m / 111195,
        "longitude": 37,
        "accuracy_m": 3,
        "speed_kmh": speed,
        "speed_accuracy_kmh": 0.1 if speed else 0,
        "source": "app",
    }


@pytest.mark.parametrize("interval_ms", [1000, 200, 100, 50])
def test_slow_departure_confirmation_is_not_lost_at_high_sample_rates(interval_ms):
    # The same 0.6 m/s manoeuvre, preceded and followed by a stationary hold.
    # At 10 Hz the old 20-fix cap never even reached the 2-second minimum.
    base = 1_700_000_000_000
    raw = [point(base + t, 0, speed=0) for t in range(0, 20_000, interval_ms)]
    departure = [point(base + t, (t - 20_000) * 0.0006)
                 for t in range(20_000, 40_000, interval_ms)]
    raw += departure
    raw += [point(base + t, 12, speed=0) for t in range(40_000, 60_000, interval_ms)]
    saved = [dict(p) for p in raw]

    result = module.filter_display(raw)
    moving = [p for p in result if base + 20_000 <= p["timestamp_ms"] < base + 40_000]

    assert moving == departure
    assert result[-1]["latitude"] == raw[-1]["latitude"]
    assert not any(p.get("display_break") for p in result)
    assert raw == saved


@pytest.mark.parametrize("interval_ms", [1000, 200, 100, 50])
def test_high_rate_uncertain_stationary_jitter_stays_one_hold(interval_ms):
    base = 1_700_000_000_000
    raw = [dict(point(base + t, ((t // 1000) % 3) - 1, speed=8),
                accuracy_m=10, speed_accuracy_kmh=12)
           for t in range(0, 40_000, interval_ms)]
    saved = [dict(p) for p in raw]
    result = module.filter_display(raw)

    assert len({(p["latitude"], p["longitude"]) for p in result}) == 1
    assert all(p["speed_kmh"] == 0 for p in result)
    assert not any(p.get("display_break") for p in result)
    assert raw == saved


@pytest.mark.parametrize("padding_ms", [30_000, 60_000, 120_000])
def test_high_rate_slow_departure_is_stable_with_wider_query_context(padding_ms):
    # The selected period crosses the departure; all queries include the
    # existing 30-second context allowance, but different surrounding holds.
    base = 1_700_000_000_000
    raw = [point(base + t, 0, speed=0) for t in range(-padding_ms, 0, 100)]
    departure = [point(base + t, t * 0.0006) for t in range(0, 20_000, 100)]
    raw += departure
    raw += [point(base + t, 12, speed=0)
            for t in range(20_000, 20_000 + padding_ms, 100)]
    selected = [p for p in module.filter_display(raw)
                if base <= p["timestamp_ms"] < base + 20_000]

    assert selected == departure
