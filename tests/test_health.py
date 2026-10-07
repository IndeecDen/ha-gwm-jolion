import importlib.util
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime, timezone

spec = importlib.util.spec_from_file_location("gwm_health_test", Path(__file__).resolve().parents[1] / "custom_components/gwm_jolion/health.py")
health = importlib.util.module_from_spec(spec)
spec.loader.exec_module(health)


def test_cloud_observation_time_never_claims_fresh_gps():
    location = {"source": "cloud", "gps_timestamp_ms": 1_700_000_000_000, "time_known": False}
    coordinator = SimpleNamespace(data={"vin": "test"}, last_update_success=False,
        last_successful_update=datetime.fromtimestamp(1_700_000_000, timezone.utc),
        trip_history=SimpleNamespace(enabled=True, location=lambda: location, last_received_ms=None))
    report = health.snapshot(coordinator, now=1_700_000_300)
    assert report["cloud_status"] == "offline"
    assert report["cloud_data_age_seconds"] == 300
    assert report["location_age_seconds"] is None
    assert report["location_freshness"] == "unknown"
    assert report["location_observed_at"] is not None


def test_delayed_upload_distinguishes_fix_age_from_receipt_age():
    history = SimpleNamespace(enabled=True, location=lambda: {"source": "app", "gps_timestamp_ms": 1_700_000_000_000, "time_known": True}, last_received_ms=1_700_000_290_000)
    coordinator = SimpleNamespace(data={}, trip_history=history)
    report = health.snapshot(coordinator, now=1_700_000_300)
    assert report["location_age_seconds"] == 300
    assert report["location_freshness"] == "stale"
    assert report["locator_receive_age_seconds"] == 10
    assert report["cloud_status"] == "unknown"
