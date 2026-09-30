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
import sys

import pytest

pytest.importorskip(
    "pytest_homeassistant_custom_component",
    reason="needs pytest-homeassistant-custom-component",
)

# The harness blocks sockets for the session, and on Windows asyncio cannot build
# its event loop without an AF_INET socket pair. That makes every test error in
# fixture setup, before a test body runs, so nothing here can run on Windows.
# CI runs this file on ubuntu-latest, where the harness works as intended.
pytestmark = pytest.mark.skipif(
    sys.platform == "win32",
    reason="pytest-homeassistant-custom-component cannot build an event loop on Windows",
)

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


@pytest.fixture(autouse=True)
def _allow_local_sockets(socket_enabled):
    """The asyncio loop is built from a socket pair; pytest-socket must allow it."""
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


async def test_tracker_reports_the_last_known_fix_when_the_cloud_is_unreachable(hass):
    """A dead cloud must not blank the position: automations still need a point."""
    entry = await _setup(hass)

    # Store a fix, then let every later cloud poll fail.
    history = hass.data[DOMAIN][entry.entry_id].trip_history
    await history.append(1_700_000_000.0, {"latitude": 55.75, "longitude": 37.62})

    client = hass.data[DOMAIN][entry.entry_id].client
    client.async_get_location.side_effect = TimeoutError("cloud unreachable")

    await hass.async_block_till_done()
    state = hass.states.get("device_tracker.test_car_mestopolozhenie")
    assert state is not None, "the tracker vanished instead of keeping its fix"
    assert state.state not in ("unknown", "unavailable")
    assert state.attributes.get("latitude") is not None


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
    coordinator.trip_history.publish()
    await hass.async_block_till_done()

    tracker = hass.states.get("device_tracker.test_car_mestopolozhenie")
    assert tracker is not None, "entity missing: the None accuracy crash is back"
    accuracy = tracker.attributes.get("gps_accuracy")
    assert accuracy is not None, "gps_accuracy must be a number, not None"
    assert isinstance(accuracy, (int, float))
