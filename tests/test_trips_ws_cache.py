"""The trip websocket: a closed window is cached, the live window never is."""
import ast
import asyncio
import logging
import time
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1] / "custom_components/gwm_jolion"
CONSTANTS = {"_LOGGER", "RECORDER_TIMEOUT", "_INFLIGHT", "_RESULT_CACHE", "_RESULT_CACHE_TTL", "_RESULT_CACHE_MAX"}
FUNCTIONS = {"_closed_window", "_timed_recorder_read", "get_trips"}


class Permissions:
    def check_entity(self, entity_id, policy):
        return True


class Registry:
    def async_get_entity_id(self, domain, platform, unique_id):
        return None

    def async_get(self, entity_id):
        return SimpleNamespace(platform="gwm_jolion", config_entry_id="car", entity_id=entity_id)


class Connection:
    def __init__(self):
        self.user = SimpleNamespace(permissions=Permissions())
        self.results, self.errors = [], []

    def send_result(self, message_id, result):
        self.results.append(result)

    def send_error(self, message_id, code, message):
        self.errors.append((code, message))


def websocket_scope():
    """Compile the handler with HA stubbed out, keeping the module constants.

    The integration is imported by Home Assistant itself, so the test pulls the
    functions out of the source instead of importing the package: the cache
    behaviour is what matters here, not the import graph.
    """
    tree = ast.parse((ROOT / "trips_ws.py").read_text(encoding="utf-8"))
    body = []
    for node in tree.body:
        targets = getattr(node, "targets", None) or [getattr(node, "target", None)]
        names = [target.id for target in targets if isinstance(target, ast.Name)]
        if isinstance(node, (ast.Assign, ast.AnnAssign)) and set(names) & CONSTANTS:
            body.append(node)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in FUNCTIONS:
            node.decorator_list = []
            body.append(node)
    scope = {
        "__name__": "trips_ws",
        "asyncio": asyncio,
        "time": time,
        "logging": logging,
        "er": SimpleNamespace(async_get=lambda hass: Registry()),
        "POLICY_READ": "read",
        "DOMAIN": "gwm_jolion",
        "dt_util": SimpleNamespace(
            parse_date=lambda text: date.fromisoformat(text),
            get_time_zone=lambda name: ZoneInfo(name) if isinstance(name, str) else name,
            now=lambda zone=None: datetime.now(zone),
        ),
    }
    exec(compile(ast.Module(body=body, type_ignores=[]), "trips_ws.py", "exec"), scope)
    return scope


def harness(reader):
    """A fake HA whose Recorder read is the only thing the test counts."""
    scope = websocket_scope()
    scope["read_history"] = reader
    history = SimpleNamespace(
        query=AsyncMock(return_value={"trips": [], "segments": [[[55, 37], [55.1, 37.1]]]}),
        enabled=True,
        retention=10,
    )
    parent = SimpleNamespace(trip_history=history)
    hass = SimpleNamespace(
        config=SimpleNamespace(components={"recorder"}, time_zone="UTC"),
        data={"gwm_jolion": {"car": parent}},
    )
    connection = Connection()
    return scope, hass, connection, history


def message(start, end):
    return {"id": 1, "entity_id": "device_tracker.car", "start": start, "end": end}


def test_closed_window_is_served_from_cache_after_one_read():
    calls = []

    async def reader(hass, entity, odometer, start, end, engine):
        calls.append(start)
        return ([], {}, {})

    scope, hass, connection, history = harness(reader)
    asyncio.run(scope["get_trips"](hass, connection, message("2024-05-01", "2024-05-02")))
    asyncio.run(scope["get_trips"](hass, connection, message("2024-05-01", "2024-05-02")))
    assert calls == ["2024-05-01"], "the second request must not touch the Recorder again"
    assert connection.results[0]["server_timings"]["cached"] is False
    assert connection.results[1]["server_timings"]["cached"] is True
    assert connection.results[1]["server_timings"]["recorder_ms"] == 0
    assert history.query.await_count == 1
    assert not connection.errors


def test_live_window_is_never_cached():
    calls = []

    async def reader(hass, entity, odometer, start, end, engine):
        calls.append(end)
        return ([], {}, {})

    scope, hass, connection, _history = harness(reader)
    today = datetime.now(ZoneInfo("UTC")).date().isoformat()
    asyncio.run(scope["get_trips"](hass, connection, message(today, today)))
    asyncio.run(scope["get_trips"](hass, connection, message(today, today)))
    assert calls == [today, today], "today still gains fixes, so it must be re-read"
    assert all(result["server_timings"]["cached"] is False for result in connection.results)


def test_cache_separates_sources_and_keeps_its_bound():
    calls = []

    async def reader(hass, entity, odometer, start, end, engine):
        calls.append(start)
        return ([], {}, {})

    scope, hass, connection, _history = harness(reader)
    scope["_RESULT_CACHE_MAX"] = 2
    for index in range(3):
        asyncio.run(scope["get_trips"](hass, connection, message(f"2024-06-0{index + 1}", f"2024-06-0{index + 2}")))
    assert len(scope["_RESULT_CACHE"]) == 2, "the cache keeps a few windows, not every window ever asked for"
    asyncio.run(scope["get_trips"](hass, connection, message("2024-06-01", "2024-06-02")))
    assert calls.count("2024-06-01") == 2, "the oldest window was evicted and is read again"


def test_cache_does_not_accumulate_per_request_fields():
    async def reader(hass, entity, odometer, start, end, engine):
        return ([], {}, {})

    scope, hass, connection, _history = harness(reader)
    asyncio.run(scope["get_trips"](hass, connection, message("2024-07-01", "2024-07-02")))
    connection.results[0]["edited_by_the_caller"] = True
    asyncio.run(scope["get_trips"](hass, connection, message("2024-07-01", "2024-07-02")))
    assert "edited_by_the_caller" not in connection.results[1], "a caller edit must not reach the cache"
    stored = next(iter(scope["_RESULT_CACHE"].values()))[1]
    assert "server_timings" not in stored, "timings describe one request, not the cached window"
    assert connection.results[1]["server_timings"]["cached"] is True


def test_closed_window_accepts_the_ha_zone_name():
    """hass.config.time_zone is a name like "Europe/Moscow", not a tzinfo object."""
    async def reader(hass, entity, odometer, start, end, engine):
        return ([], {}, {})

    scope, hass, connection, _history = harness(reader)
    hass.config.time_zone = "Europe/Moscow"
    asyncio.run(scope["get_trips"](hass, connection, message("2024-05-01", "2024-05-02")))
    assert not connection.errors, "the handler must not fail on the string zone real HA stores"
    assert connection.results[0]["server_timings"]["cached"] is False
