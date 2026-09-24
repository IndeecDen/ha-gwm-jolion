"""Independent location polling without live vehicle requests."""
import asyncio
import ast
from datetime import timedelta
from types import SimpleNamespace
import logging
import time

import pytest

from test_stability import methods, ApiError, AuthFailed, UpdateFailed, ROOT


@pytest.mark.parametrize("options,data,expected", [
    ({"gps_interval":10},{},10),
    ({"gps_interval":60},{"poll_interval":300},60),
    ({"poll_interval":120},{},120),
    ({},{"poll_interval":180},180),
    ({},{},300),
    ({"gps_interval":1},{},10),
])
def test_tracker_setup_preserves_saved_interval(options, data, expected):
    node=next(n for n in ast.parse((ROOT/"device_tracker.py").read_text(encoding="utf-8")).body if isinstance(n,ast.AsyncFunctionDef) and n.name=="async_setup_entry")
    captured=[]
    def coordinator(parent,interval):
        captured.append(interval)
        return SimpleNamespace(async_add_listener=lambda callback:lambda:None)
    scope=dict(DOMAIN="gwm_jolion",CONF_GPS_INTERVAL="gps_interval",CONF_POLL_INTERVAL="poll_interval",DEFAULT_POLL_INTERVAL=300,MIN_GPS_INTERVAL=10,GwmGpsCoordinator=coordinator,GwmJolionLocationTracker=lambda gps:gps)
    tree=ast.Module(body=ast.parse("from __future__ import annotations").body+[node],type_ignores=[])
    exec(compile(tree,"tracker_setup","exec"),scope)
    entry=SimpleNamespace(entry_id="car",options=options,data=data,async_on_unload=lambda callback:None)
    hass=SimpleNamespace(data={"gwm_jolion":{"car":object()}})
    asyncio.run(scope["async_setup_entry"](hass,entry,lambda entities:None))
    assert captured==[expected]


def test_location_request_uses_only_status():
    calls = []
    async def login(): calls.append("login")
    async def status(vin):
        calls.append(vin)
        return {"latitude": 55.1, "longitude": 37.2}
    method = methods("api.py", "GwmJolionApiClient", ["async_get_location"], {"build_state":lambda *args:{"mileage_total":123}})["async_get_location"]
    result = asyncio.run(method(SimpleNamespace(_ensure_login=login, _get_last_status=status), "test-vin"))
    assert calls == ["login", "test-vin"]
    assert result == {"latitude": 55.1, "longitude": 37.2, "gps_accuracy": 50, "odometer":123}


def test_gps_updates_without_overwriting_full_data_and_recovers():
    scope = dict(asyncio=asyncio, timedelta=timedelta, time=time, ConfigEntryAuthFailed=AuthFailed,
                 GwmJolionApiError=ApiError, UpdateFailed=UpdateFailed)
    method = methods("gps.py", "GwmGpsCoordinator", ["_async_update_data"], scope)["_async_update_data"]
    async def run():
        failure = None
        async def location(vin):
            assert vin == "car"
            if failure: raise failure
            return {"latitude": 56, "longitude": 38}
        parent = SimpleNamespace(data={"vin":"car", "location":{"latitude":55}, "state":{"fuel":30}},
                                 client=SimpleNamespace(async_get_location=location),last_update_success=True)
        gps = SimpleNamespace(parent=parent, poll_interval=10)
        result = await method(gps)
        assert result["location"]["latitude"] == 56
        assert parent.data["location"]["latitude"] == 55
        assert result["state"] == parent.data["state"]
        for failure in [ApiError("secret",code="550004"), TimeoutError()]:
            with pytest.raises(UpdateFailed) as err: await method(gps)
            assert "secret" not in str(err.value)
            assert parent.last_update_success
        assert parent.gps_update_health["consecutive_failures"] == 2
        assert gps.update_interval.total_seconds() == 60
        for _ in range(8):
            with pytest.raises(UpdateFailed): await method(gps)
        assert gps.update_interval.total_seconds() == 300
        gps.poll_interval = 600
        with pytest.raises(UpdateFailed): await method(gps)
        assert gps.update_interval.total_seconds() == 600
        gps.poll_interval = 10
        failure = AuthFailed()
        with pytest.raises(AuthFailed): await method(gps)
        failure = None
        assert (await method(gps))["location"]["longitude"] == 38
        assert parent.gps_update_health["consecutive_failures"] == 0
        assert parent.gps_update_health["last_success"] > 0
        assert gps.update_interval.total_seconds() == 10
        assert parent.gps_update_health["effective_interval_seconds"] == 10
    asyncio.run(run())


def test_history_storage_failure_does_not_break_gps():
    scope = dict(asyncio=asyncio, timedelta=timedelta,time=time,_LOGGER=logging.getLogger(__name__),ConfigEntryAuthFailed=AuthFailed,
                 GwmJolionApiError=ApiError,UpdateFailed=UpdateFailed)
    method=methods("gps.py","GwmGpsCoordinator",["_async_update_data"],scope)["_async_update_data"]
    async def run():
        async def location(vin): return {"latitude":55,"longitude":37,"odometer":100}
        async def append(*args): raise OSError("disk full")
        parent=SimpleNamespace(data={"vin":"test"},client=SimpleNamespace(async_get_location=location),
                               trip_history=SimpleNamespace(append=append))
        assert (await method(SimpleNamespace(parent=parent, poll_interval=10)))["location"]["latitude"]==55
        assert parent.gps_update_health["history_write_failed"] is True
    asyncio.run(run())
