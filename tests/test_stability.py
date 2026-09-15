"""Recovery tests against actual methods, with no network or HA runtime."""
import ast
import asyncio
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from types import SimpleNamespace
import time
from urllib.parse import urlencode

import pytest

ROOT = Path(__file__).resolve().parents[1] / "custom_components/gwm_jolion"


class AuthFailed(Exception): pass
class ApiError(Exception):
    def __init__(self, message, *, code=None, **context):
        super().__init__(message)
        self.code = code
        self.__dict__.update(context)
class UpdateFailed(Exception): pass


def test_start_guard_forces_refresh_and_rejects_stale_data():
    scope={"HomeAssistantError":RuntimeError}
    refresh=methods("coordinator.py", "GwmJolionCoordinator", ["async_request_refresh_with_source"], scope)["async_request_refresh_with_source"]
    async def run():
        calls=[]
        async def direct(): calls.append("direct")
        async def debounced(): calls.append("debounced")
        obj=SimpleNamespace(_next_update_source="poll",async_refresh=direct,async_request_refresh=debounced,last_update_success=False)
        with pytest.raises(RuntimeError): await refresh(obj,"remote_start_guard")
        assert calls == ["direct"] and obj._next_update_source == "poll"
        obj.last_update_success=True
        await refresh(obj,"manual_button")
        assert calls == ["direct","debounced"]
    asyncio.run(run())


def methods(file, classname, names, scope):
    cls = next(n for n in ast.parse((ROOT / file).read_text(encoding="utf-8")).body if isinstance(n, ast.ClassDef) and n.name == classname)
    nodes = ast.parse("from __future__ import annotations").body + [n for n in cls.body if isinstance(n, ast.AsyncFunctionDef) and n.name in names]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), file, "exec"), scope)
    return {name: scope[name] for name in names}


def client(reply):
    scope = dict(asyncio=asyncio, time=time, json=json, urlencode=urlencode, BASE_URL="https://example.invalid", ENDPOINT_LOGIN="login",
        ClientError=ConnectionError, GwmJolionApiError=ApiError, ConfigEntryAuthFailed=AuthFailed,
        is_auth_error_code=lambda code: code in {"401", "308001"}, _LOGGER=logging.getLogger(__name__))
    cls = type("Client", (), methods("api.py", "GwmJolionApiClient", ["async_login", "_ensure_login", "_request"], scope))
    obj = cls()
    obj._access_token = "old"
    obj._login_lock = asyncio.Lock()
    obj._phone = obj._password = obj._device_id = obj._country = obj._country_code = "test"
    obj._headers = lambda *args: {"token": obj._access_token}
    class Response:
        async def __aenter__(self):
            self.status, body = await reply(self.url, self.headers)
            self.body = body if isinstance(body, str) else json.dumps(body)
            return self
        async def __aexit__(self, *args): pass
        async def text(self): return self.body
    def request(method, url, **kwargs):
        response = Response(); response.url = url; response.headers = kwargs["headers"]
        return response
    obj._session = SimpleNamespace(request=request)
    return obj


def test_parallel_expired_token_renews_once():
    async def run():
        logins = []
        async def reply(url, headers):
            if url.endswith("login"):
                logins.append(1); await asyncio.sleep(.005)
                return 200, {"code": "000000", "data": {"accessToken": "new"}}
            if headers["token"] == "old":
                await asyncio.sleep(.001)
                return 401, "not json"
            return 200, {"code": "000000", "data": {}}
        obj = client(reply)
        await asyncio.gather(obj._request("GET", "status"), obj._request("GET", "status"))
        assert len(logins) == 1 and obj._access_token == "new"
    asyncio.run(run())


def test_field_error_550004_recovers_reads_with_one_shared_login():
    async def run():
        logins=[]
        async def reply(url, headers):
            if url.endswith("login"):
                logins.append(1)
                await asyncio.sleep(.005)
                return 200, {"code":"000000", "data":{"accessToken":"fresh"}}
            if headers["token"] == "old":
                await asyncio.sleep(.001)
                return 200, {"code":"550004"}
            return 200, {"code":"000000", "data":{}}
        obj=client(reply)
        results=await asyncio.gather(obj._request("GET","status"),obj._request("GET","status"))
        assert len(logins)==1 and all(r["code"]=="000000" for r in results)
    asyncio.run(run())


def test_persistent_550004_is_bounded_and_never_replays_post():
    async def run():
        calls=[]
        async def reply(url,headers):
            calls.append(url)
            if url.endswith("login"):return 200,{"code":"000000","data":{"accessToken":"fresh"}}
            return 200,{"code":"550004"}
        obj=client(reply)
        with pytest.raises(ApiError) as err: await obj._request("GET","status")
        assert calls==["https://example.invalidstatus","https://example.invalidlogin","https://example.invalidstatus"]
        assert err.value.endpoint=="status" and err.value.http_status==200
        with pytest.raises(ApiError): await obj._request("GET","status")
        assert len(calls)==4  # No second login during cooldown.
        with pytest.raises(ApiError): await obj._request("POST","command")
        assert len(calls)==5  # Exactly one send, no login/replay.
        obj._last_read_recovery-=301
        with pytest.raises(ApiError): await obj._request("GET","status")
        assert len(calls)==8  # Recovery is permitted again after cooldown.
    asyncio.run(run())


@pytest.mark.parametrize("status,body", [(503, "maintenance"), (429, "rate limit"), (200, []), (200, {}), (200, "broken")])
def test_transient_login_errors_do_not_require_reauthentication(status, body):
    async def run():
        async def reply(*args): return status, body
        obj = client(reply); obj._access_token = None
        with pytest.raises(ApiError): await obj._ensure_login()
    asyncio.run(run())


def test_rejected_renewed_token_retries_next_poll_but_bad_password_is_auth_failure():
    async def run():
        async def reply(url, headers):
            if url.endswith("login"): return 200, {"code":"000000", "data":{"accessToken":"new"}}
            return 200, {"code":"401"}
        obj = client(reply)
        with pytest.raises(ApiError): await obj._request("GET", "status")
        assert obj._access_token is None
        async def bad_password(*args): return 200, {"code":"308001", "description":"invalid login"}
        obj = client(bad_password); obj._access_token = None
        with pytest.raises(AuthFailed): await obj._ensure_login()
    asyncio.run(run())


def test_refresh_failure_is_recorded_and_next_attempt_recovers():
    scope = dict(asyncio=asyncio, time=time, datetime=datetime, timezone=timezone, VERSION="test",
        ConfigEntryAuthFailed=AuthFailed, UpdateFailed=UpdateFailed, append_jsonl=lambda *args: None, _LOGGER=logging.getLogger(__name__))
    update = methods("coordinator.py", "GwmJolionCoordinator", ["_async_update_data"], scope)["_async_update_data"]
    async def run():
        records=[]
        async def append(fn,path,record): records.append(record)
        async def fail(): raise ApiError("sensitive message must not be captured",code="503")
        obj=SimpleNamespace(_next_update_source="poll", _async_update_data_impl=fail, update_health={"consecutive_failures":0},
            protocol_capture_enabled=True,protocol_capture_path="unused",protocol_capture_sequence=0,hass=SimpleNamespace(async_add_executor_job=append))
        with pytest.raises(UpdateFailed): await update(obj)
        assert records[0]["type"] == "refresh_error" and "sensitive" not in json.dumps(records)
        async def good(): return {"state":{}}
        obj._async_update_data_impl=good
        assert await update(obj) == {"state":{}}
        assert obj.update_health["consecutive_failures"] == 0
        assert obj.update_health["last_error"]["code"] == "503"
        async def pending(): await asyncio.sleep(60)
        scope["asyncio"] = SimpleNamespace(timeout=lambda seconds: asyncio.timeout(.005))
        obj._async_update_data_impl=pending
        with pytest.raises(UpdateFailed): await update(obj)
        assert obj.update_health["last_error"]["type"] == "TimeoutError"
    asyncio.run(run())
