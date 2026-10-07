"""Set the integration up the way a real Home Assistant instance does.

The unit tests load single modules by path, so nothing ever executed
`async_setup_entry`.  That is how a missing import shipped: the failure only
appeared on the user's instance, as a bare traceback and a device_tracker entity
that Home Assistant reported as "no longer provided by gwm_jolion" while its
registry row sat there unused.

This file runs the real entry setup through pytest-homeassistant-custom-component.
It needs that plugin, so it skips in the plain test venv and runs in .venv-ha.

Run: .venv-ha\\Scripts\\python.exe -m pytest -q tests/ha
"""
from unittest.mock import AsyncMock, patch
from pathlib import Path
import sys
import os

import pytest

pytest.importorskip(
    "pytest_homeassistant_custom_component",
    reason="needs pytest-homeassistant-custom-component",
)

def _environment_can_set_the_entry_up() -> bool:
    """Whether this virtualenv provides what setting the entry up needs.

    Two things have to be present and neither is about this integration:

    * `hass_frontend`, because the `frontend` component builds each static path as
      `root / name` and needs `where()` to be a Path. The package ships from Home
      Assistant's own index, which is not reachable everywhere.
    * `OptionsFlowWithReload`, which `config_flow` builds on. A virtualenv older
      than the integration fails with a bare import error instead.

    The alternative - skipping on `sys.platform == "win32"` - hid both, and that
    skip is what let a broken import reach the user's instance before.
    """
    try:
        import hass_frontend
        from homeassistant import config_entries
    except Exception:
        return False
    return isinstance(hass_frontend.where(), Path) and hasattr(config_entries, "OptionsFlowWithReload")


# Windows uses tools/run_ha_tests.py for its local asyncio socketpair.
pytestmark = pytest.mark.skipif(
    not _environment_can_set_the_entry_up(),
    reason="this virtualenv cannot set a Home Assistant config entry up (frontend assets or Home Assistant version)",
)
if os.environ.get("GWM_HA_STRICT") == "1" and not _environment_can_set_the_entry_up():
    raise RuntimeError("HA/frontend environment is incompatible; install tests/ha/requirements.txt")

pytest_plugins = "pytest_homeassistant_custom_component"

from homeassistant.config_entries import ConfigEntryState  # noqa: E402
from pytest_homeassistant_custom_component.common import MockConfigEntry  # noqa: E402

from custom_components.gwm_jolion.const import DOMAIN  # noqa: E402

ENTRY_DATA = {
    "phone": "+70000000000",
    "password": "secret",
    "device_id": "test-device",
    "country": "RU",
    "country_code": "+7",
}

LOCATOR_OPTIONS = {
    "golion_locator_enabled": True,
    "golion_locator_transport": "https",
    "golion_locator_vehicle_id": "jolion",
    "golion_locator_upload_key": "u" * 64,
    "golion_locator_relay_interval": 300,
    "gps_interval": 10,
    "poll_interval": 30,
    "protocol_capture_enabled": False,
}

CLOUD_PAYLOAD = {
    "vin": "LVXTESTVIN0000001",
    "vehicle_name": "Test Car",
    "location": {"latitude": 52.6188, "longitude": 39.6089, "gps_accuracy": 2.2},
    "state": {"mileage_total": 1234.5},
}


@pytest.fixture(autouse=True)
def _auto_enable_custom_integrations(enable_custom_integrations):
    yield


def _fake_client(*_args, **_kwargs):
    client = AsyncMock()
    client.async_update.return_value = dict(CLOUD_PAYLOAD)
    client.async_get_location.return_value = dict(CLOUD_PAYLOAD["location"])
    return client


async def _setup(hass, options=None):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=ENTRY_DATA,
        options={**LOCATOR_OPTIONS, **(options or {})},
        version=2,
        minor_version=1,
    )
    entry.add_to_hass(hass)
    with patch("custom_components.gwm_jolion.GwmJolionApiClient", _fake_client):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


async def test_entry_reaches_loaded_and_creates_the_device_tracker(hass):
    """The tracker is the entity automations depend on; it must exist after setup."""
    entry = await _setup(hass)

    assert entry.state is ConfigEntryState.LOADED, (
        f"setup did not finish: {entry.state}, reason={entry.reason}"
    )
    trackers = [
        state for state in hass.states.async_all("device_tracker")
        if state.entity_id.startswith("device_tracker.test_car_")
    ]
    assert trackers, [
        state.entity_id for state in hass.states.async_all()
    ]


async def test_cloud_only_setup_creates_available_tracker(hass):
    entry = await _setup(hass, {"golion_locator_enabled": False})
    assert entry.state is ConfigEntryState.LOADED
    tracker = hass.states.get("device_tracker.test_car_mestopolozhenie")
    assert tracker is not None and tracker.state not in ("unknown", "unavailable")
    assert tracker.attributes["latitude"] == CLOUD_PAYLOAD["location"]["latitude"]


async def test_tracker_reports_the_last_known_fix_when_the_cloud_is_unreachable(hass):
    """A dead cloud must not blank the position: automations still need a point."""
    entry = await _setup(hass)

    # Store a fix, then let every later cloud poll fail.
    history = hass.data[DOMAIN][entry.entry_id].trip_history
    await history.append(1_700_000_000.0, {"latitude": 55.75, "longitude": 37.62})

    client = hass.data[DOMAIN][entry.entry_id].client
    client.async_get_location.side_effect = TimeoutError("cloud unreachable")
    await history.gps.async_refresh()
    await hass.async_block_till_done()
    state = hass.states.get("device_tracker.test_car_mestopolozhenie")
    assert state is not None, "the tracker vanished instead of keeping its fix"
    assert state.state not in ("unknown", "unavailable")
    assert state.attributes.get("latitude") is not None

    client.async_get_location.side_effect = None
    client.async_get_location.return_value = {"latitude": 55.76, "longitude": 37.63}
    await history.gps.async_refresh()
    assert hass.data[DOMAIN][entry.entry_id].gps_update_health["consecutive_failures"] == 0


async def test_unload_and_reload_recreates_entities_without_duplicates(hass):
    entry = await _setup(hass)
    before = {s.entity_id for s in hass.states.async_all("device_tracker")}
    old = hass.data[DOMAIN][entry.entry_id]
    with patch("custom_components.gwm_jolion.GwmJolionApiClient", _fake_client):
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert hass.data[DOMAIN][entry.entry_id] is not old
    assert {s.entity_id for s in hass.states.async_all("device_tracker")} == before
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.entry_id not in hass.data[DOMAIN]


async def test_health_entities_stay_readable_during_cloud_failure(hass):
    entry = await _setup(hass)
    coordinator = hass.data[DOMAIN][entry.entry_id]
    coordinator.client.async_update.side_effect = TimeoutError("offline")
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    cloud = hass.states.get("sensor.test_car_sviaz_s_oblakom_gwm")
    assert cloud.state == "offline"
    assert cloud.attributes["cloud_last_update"] is not None
    source = hass.states.get("sensor.test_car_istochnik_koordinat")
    assert source.state == "cloud"
    assert source.attributes["location_freshness"] == "unknown"
    coordinator.client.async_update.side_effect = None
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(cloud.entity_id).state == "online"


async def test_diagnostics_redact_credentials_identifiers_and_coordinates(hass):
    import json
    from custom_components.gwm_jolion.diagnostics import async_get_config_entry_diagnostics
    entry = await _setup(hass)
    coordinator = hass.data[DOMAIN][entry.entry_id]
    coordinator.data["vehicle"] = {"vin": "PRIVATE-VIN", "latitude": 55.123456, "accessToken": "PRIVATE-TOKEN"}
    payload = await async_get_config_entry_diagnostics(hass, entry)
    text = json.dumps(payload)
    assert "PRIVATE-VIN" not in text and "PRIVATE-TOKEN" not in text and "55.123456" not in text
    assert "secret" not in text and "u" * 64 not in text
    assert payload["health"]["cloud_status"] == "online"


async def test_locator_survives_reload_while_cloud_is_offline(hass):
    import time
    entry = await _setup(hass)
    history = hass.data[DOMAIN][entry.entry_id].trip_history
    point = {"id": "restart-fix-0001", "timestamp_ms": int(time.time()*1000),
             "latitude": 55.75, "longitude": 37.62, "accuracy_m": 5}
    await history.ingest([point])
    received = history.last_received_ms
    def offline(*args, **kwargs):
        client = _fake_client()
        client.async_update.side_effect = TimeoutError("offline during restart")
        return client
    with patch("custom_components.gwm_jolion.GwmJolionApiClient", offline):
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    restored = hass.data[DOMAIN][entry.entry_id].trip_history
    assert restored.last_received_ms == received
    assert restored.latest["id"] == point["id"]
    tracker = hass.states.get("device_tracker.test_car_mestopolozhenie")
    assert tracker.attributes["latitude"] == point["latitude"]
    assert tracker.attributes["location_source"] == "app"


async def test_accuracy_is_a_number_even_when_the_cloud_reports_none(hass):
    """Regression: a None accuracy took the whole entity out of the state machine.

    Home Assistant compares `zone_dist - zone_radius < radius` with this value, so
    None raised TypeError while the state was written and Home Assistant refused
    to add the entity. Cloud fixes always report no accuracy, so this is the
    normal parked-car case, not an edge case.
    """
    entry = await _setup(hass)

    # A cloud position carries no measured accuracy.
    coordinator = hass.data[DOMAIN][entry.entry_id]
    import time
    await coordinator.trip_history.append(time.time(), {"latitude": 55.75, "longitude": 37.62, "gps_accuracy": None})
    coordinator.trip_history.publish()
    await hass.async_block_till_done()

    tracker = hass.states.get("device_tracker.test_car_mestopolozhenie")
    assert tracker is not None, "entity missing: the None accuracy crash is back"
    accuracy = tracker.attributes.get("gps_accuracy")
    assert accuracy is not None, "gps_accuracy must be a number, not None"
    assert isinstance(accuracy, (int, float))
