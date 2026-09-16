"""Independent location polling without live vehicle requests."""
import asyncio
from types import SimpleNamespace
import logging
import time

import pytest

from test_stability import methods, ApiError, AuthFailed, UpdateFailed


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
    scope = dict(asyncio=asyncio, ConfigEntryAuthFailed=AuthFailed,
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
        gps = SimpleNamespace(parent=parent)
        result = await method(gps)
        assert result["location"]["latitude"] == 56
        assert parent.data["location"]["latitude"] == 55
        assert result["state"] == parent.data["state"]
        for failure in [ApiError("secret",code="550004"), TimeoutError()]:
            with pytest.raises(UpdateFailed) as err: await method(gps)
            assert "secret" not in str(err.value)
            assert parent.last_update_success
        failure = AuthFailed()
        with pytest.raises(AuthFailed): await method(gps)
        failure = None
        assert (await method(gps))["location"]["longitude"] == 38
    asyncio.run(run())


def test_history_storage_failure_does_not_break_gps():
    scope = dict(asyncio=asyncio,time=time,_LOGGER=logging.getLogger(__name__),ConfigEntryAuthFailed=AuthFailed,
                 GwmJolionApiError=ApiError,UpdateFailed=UpdateFailed)
    method=methods("gps.py","GwmGpsCoordinator",["_async_update_data"],scope)["_async_update_data"]
    async def run():
        async def location(vin): return {"latitude":55,"longitude":37,"odometer":100}
        async def append(*args): raise OSError("disk full")
        parent=SimpleNamespace(data={"vin":"test"},client=SimpleNamespace(async_get_location=location),
                               trip_history=SimpleNamespace(append=append))
        assert (await method(SimpleNamespace(parent=parent)))["location"]["latitude"]==55
    asyncio.run(run())
