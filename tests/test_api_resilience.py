"""Offline resilience regressions exercising the actual API methods."""
import asyncio
import logging
from types import SimpleNamespace

import pytest

from test_stability import ApiError, AuthFailed, client, methods


def install_methods(obj, *names):
    scope = obj._request.__func__.__globals__
    scope.setdefault("ENDPOINT_T5_CTRL_RESULT", "result")
    scope.setdefault("classify_t5_result_code", lambda code: "error" if str(code) == "3" else "success")
    for name, method in methods("api.py", "GwmJolionApiClient", names, scope).items():
        setattr(obj, name, method.__get__(obj))
    return scope


@pytest.mark.parametrize("failure", [TimeoutError("lost response"), ConnectionError("offline"), 429, 503])
@pytest.mark.parametrize("login", [False, True])
def test_safe_requests_retry_transient_failures_with_bounded_jitter(failure, login):
    async def run():
        calls, delays = [], []
        async def reply(url, headers):
            calls.append((url, headers))
            if len(calls) < 3:
                if isinstance(failure, Exception):
                    raise failure
                return failure, "temporary"
            return 200, {"code": "000000", "data": {"accessToken": "fresh"}}
        obj = client(reply)
        async def sleep(delay): delays.append(delay)
        obj._request.__func__.__globals__["asyncio"] = SimpleNamespace(sleep=sleep)
        if login:
            obj._access_token = None
            await obj.async_login()
            assert obj._access_token == "fresh"
        else:
            assert (await obj._request("GET", "status"))["code"] == "000000"
        assert len(calls) == 3
        assert len(delays) == 2
        assert 0.25 <= delays[0] <= 0.5
        assert 0.5 <= delays[1] <= 1.0
    asyncio.run(run())


@pytest.mark.parametrize("method,path", [("GET", "status"), ("POST", "login"), ("POST", "command"), ("POST", "settings")])
def test_retry_budget_never_replays_ambiguous_writes(method, path):
    async def run():
        calls, delays = [], []
        async def reply(*args):
            calls.append(1)
            raise TimeoutError("possibly accepted")
        obj = client(reply)
        async def sleep(delay): delays.append(delay)
        obj._request.__func__.__globals__["asyncio"] = SimpleNamespace(sleep=sleep)
        with pytest.raises(ApiError) as error:
            await obj._request(method, path, with_token=path != "login")
        assert error.value.category == "timeout"
        expected = 3 if method == "GET" or path == "login" else 1
        assert len(calls) == expected
        assert len(delays) == expected - 1
    asyncio.run(run())


def test_command_poll_deadline_bounds_a_stalled_request():
    async def run():
        obj = client(lambda *args: None)
        scope = install_methods(obj, "async_poll_t5_result")
        scope["asyncio"] = asyncio
        cancelled = []
        async def stalled(*args, **kwargs):
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.append(True)
        obj._request = stalled
        with pytest.raises(ApiError) as error:
            await asyncio.wait_for(obj.async_poll_t5_result("vin", "request", "1", timeout=0.03, interval=0), timeout=0.3)
        assert error.value.category == "timeout"
        assert cancelled == [True]
    asyncio.run(run())


def test_command_poll_does_not_expose_server_message():
    async def run():
        obj = client(lambda *args: None)
        install_methods(obj, "async_poll_t5_result")
        async def rejected(*args, **kwargs):
            return {"data": [{"remoteType": "1", "resultCode": "3", "resultMsg": "synthetic-secret-from-server"}]}
        obj._request = rejected
        with pytest.raises(ApiError) as error:
            await obj.async_poll_t5_result("vin", "request", "1", timeout=0.03, interval=0)
        assert "synthetic-secret" not in str(error.value)
        assert error.value.category == "command_rejected"
    asyncio.run(run())


@pytest.mark.parametrize("data", [["unexpected"], "token", 12, {"accessToken": ["secret"]}, {"accessToken": 42}, {"accessToken": " "}, None])
def test_login_rejects_malformed_token_without_auth_failure(data):
    async def run():
        async def reply(*args): return 200, {"code": "000000", "data": data}
        obj = client(reply)
        obj._access_token = None
        with pytest.raises(ApiError) as error:
            await obj.async_login()
        assert error.value.category == "invalid_structure"
        assert obj._access_token is None
    asyncio.run(run())
