"""The trips card WebSocket path with both GPS sources present.

Regression: cloud fixes carry accuracy_m = None. The parking merge compared that
with a number, every _query() raised, and the card reported
"история поездок недоступна" with an empty map. The unit fixtures use an empty
cloud database, so this exercises the mixed case the card really hits.

Run: .venv\\Scripts\\python.exe -m pytest -q tests/test_locator_query_mixed.py
"""
import asyncio
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_locator import make_history

NOW = 1_700_000_000_000
SLEEP = 8 * 3600
MILEAGE = 78502.0


def app_point(offset_ms, x=0.0, speed=0.0, accuracy=5.0):
    return {"id": f"app-{offset_ms}", "timestamp_ms": NOW + offset_ms,
            "latitude": 55.0 + x / 111195, "longitude": 37.0,
            "accuracy_m": accuracy, "speed_kmh": speed,
            "speed_accuracy_kmh": None, "bearing": None, "altitude_m": None}


def add_cloud(history, rows):
    """Write cloud observations, exactly as the GPS poller does."""
    db = history._connect()
    db.executemany("INSERT OR REPLACE INTO points VALUES (?, ?, ?, ?)", rows)
    db.commit()
    db.close()


def parked_app_points(count, offset_s=0):
    return [app_point((offset_s + i) * 1000) for i in range(count)]


def run(coroutine):
    with tempfile.TemporaryDirectory() as folder:
        asyncio.run(coroutine(Path(folder)))


def test_query_with_app_and_cloud_points_returns_a_map():
    async def scenario(tmp_path):
        _, history = make_history(tmp_path)
        await history.initialize()
        await history.ingest([*parked_app_points(400), *parked_app_points(400, 400 + SLEEP)])
        add_cloud(history, [
            (NOW / 1000 + 399, 55.0, 37.0, MILEAGE),
            (NOW / 1000 + 400 + SLEEP + 5, 55.0, 37.0, MILEAGE),
        ])
        result = await history.query("2023-11-14", "2023-11-15", "UTC")
        assert isinstance(result.get("segments"), list)
        assert result["segments"], "маршрут пуст, карта не отрисовалась бы"
        assert result["samples"] > 0
        spots = result.get("parking_spots") or []
        assert spots, "ни одной стоянки не вернулось"
        assert any(s.get("inferred") for s in spots), (
            "сон не распознан: " + repr([(s.get("start"), s.get("inferred")) for s in spots])
        )

    run(scenario)


def test_query_survives_cloud_points_without_odometer():
    async def scenario(tmp_path):
        _, history = make_history(tmp_path)
        await history.initialize()
        await history.ingest([*parked_app_points(300), *parked_app_points(300, 300 + SLEEP)])
        add_cloud(history, [(NOW / 1000 + 299, 55.0, 37.0, None)])
        result = await history.query("2023-11-14", "2023-11-15", "UTC")
        assert isinstance(result.get("segments"), list)
        assert result["parking_spots"] is not None

    run(scenario)


def test_query_survives_a_period_with_only_cloud_points():
    async def scenario(tmp_path):
        _, history = make_history(tmp_path)
        await history.initialize()
        add_cloud(history, [
            (NOW / 1000 + i * 2, 55.0 + i * 0.0001, 37.0, 100.0 + i * 0.01)
            for i in range(200)
        ])
        result = await history.query("2023-11-14", "2023-11-15", "UTC")
        assert result["samples"] > 0

    run(scenario)


def test_query_survives_only_app_points():
    async def scenario(tmp_path):
        _, history = make_history(tmp_path)
        await history.initialize()
        await history.ingest(parked_app_points(600))
        result = await history.query("2023-11-14", "2023-11-15", "UTC")
        assert result["segments"]

    run(scenario)


def test_repeated_local_query_uses_short_cache_and_new_app_points_invalidate_it():
    async def scenario(tmp_path):
        _, history = make_history(tmp_path)
        await history.initialize()
        await history.ingest(parked_app_points(4))
        first=await history.query("2023-11-14","2023-11-14","UTC")
        assert first["history_profile"]["cache"]=="miss"
        second=await history.query("2023-11-14","2023-11-14","UTC")
        assert second["history_profile"]["cache"]=="hit"
        assert second["segments"] is first["segments"],"cache hit must not deep-copy the large route payload"
        assert "playback_ms" in first["history_profile"]
        await history.ingest([app_point(10_000,x=100)])
        third=await history.query("2023-11-14","2023-11-14","UTC")
        assert third["history_profile"]["cache"]=="miss"
    run(scenario)


def test_parallel_identical_queries_share_one_history_calculation():
    async def scenario(tmp_path):
        _, history = make_history(tmp_path)
        await history.initialize()
        await history.ingest(parked_app_points(50))
        original=history._query
        calls=0
        def counted(*args,**kwargs):
            nonlocal calls
            calls+=1
            return original(*args,**kwargs)
        history._query=counted
        results=await asyncio.gather(*[
            history.query("2023-11-14","2023-11-14","UTC") for _ in range(5)
        ])
        assert calls==1
        assert all(result["segments"]==results[0]["segments"] for result in results)
    run(scenario)


def test_websocket_exposes_server_phase_timings():
    """Browser diagnostics need Recorder and history processing as separate phases."""
    import ast
    from types import SimpleNamespace

    root=Path(__file__).resolve().parents[1]/"custom_components/gwm_jolion/trips_ws.py"
    node=next(n for n in ast.parse(root.read_text(encoding="utf-8")).body if isinstance(n,ast.AsyncFunctionDef))
    node.decorator_list=[]
    scope={"DOMAIN":"gwm_jolion","POLICY_READ":"read","er":SimpleNamespace(
        async_get=lambda hass:SimpleNamespace(async_get=lambda entity:SimpleNamespace(config_entry_id="car",platform="gwm_jolion"),async_get_entity_id=lambda *args:None)),
        "asyncio":asyncio,"perf_counter":iter(range(100)).__next__,"_LOGGER":SimpleNamespace(warning=lambda *args:None)}
    exec(compile(ast.Module(body=[node],type_ignores=[]),"trips_ws","exec"),scope)
    async def scenario():
        async def query(*args):return {"samples":4,"segments":[[[55,37],[55.1,37.1]]],"source_counts":{"app":2,"cloud":2}}
        parent=SimpleNamespace(trip_history=SimpleNamespace(query=query,enabled=True,retention=90))
        hass=SimpleNamespace(data={"gwm_jolion":{"car":parent}},config=SimpleNamespace(time_zone="UTC",components=set()))
        results=[];errors=[]
        connection=SimpleNamespace(user=SimpleNamespace(permissions=SimpleNamespace(check_entity=lambda *args:True)),send_error=lambda *args:errors.append(args),send_result=lambda *args:results.append(args))
        await scope["get_trips"](hass,connection,{"id":1,"entity_id":"device_tracker.car","start":"2023-11-14","end":"2023-11-14"})
        assert not errors
        timings=results[0][1]["server_timings"]
        assert set(timings)=={"recorder_ms","history_processing_ms","total_ms"}
        assert all(isinstance(value,int) and value>=0 for value in timings.values())
        assert results[0][1]["diagnostics"]["source_counts"]=={"app":2,"cloud":2}
    asyncio.run(scenario())
