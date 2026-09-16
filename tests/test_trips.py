"""Calendar, persistence, gaps and authorization of trip history."""
import ast
import asyncio
from datetime import datetime
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from functools import partial
from datetime import timezone

import pytest

ROOT = Path(__file__).resolve().parents[1] / "custom_components/gwm_jolion"
spec = importlib.util.spec_from_file_location("trip_history", ROOT / "trips.py")
trips = importlib.util.module_from_spec(spec)
spec.loader.exec_module(trips)


def stamp(value):
    return datetime.fromisoformat(value).timestamp()


def test_calendar_uses_ha_timezone_and_dst():
    low, high = trips.period("2026-03-29", "2026-03-29", "Europe/Berlin")
    assert high-low == 23*3600
    low, high = trips.period("2026-10-25", "2026-10-25", "Europe/Berlin")
    assert high-low == 25*3600
    assert trips.period("2026-09-16", "2026-09-16", "Europe/Moscow")[0] == stamp("2026-09-15T21:00:00+00:00")
    for first,last in [("bad","2026-09-16"),("2026-09-17","2026-09-16"),("2020-01-01","2026-01-01")]:
        with pytest.raises(ValueError): trips.period(first,last,"UTC")


def test_odometer_midnight_reset_gaps_and_gps_fallback():
    base = stamp("2026-09-15T23:59:00+00:00")
    rows = [(base,55,37,100),(base+60,55,37.01,101),(base+120,55,37.02,102),
            (base+180,55,37.03,1),(base+240,55,37.04,2),(base+1000,55,37.05,3)]
    result = trips.summarize(rows,"2026-09-15","2026-09-16","UTC")
    assert result["days"][1]["km"] == 3  # No midnight or odometer-reset jump.
    assert result["days"][1]["gaps"] == 1
    assert len(result["segments"]) == 3
    rows = [(base,55,37,None),(base+60,55,37.01,None),(base+120,0,100,None)]
    result = trips.summarize(rows,"2026-09-15","2026-09-16","Europe/Moscow")
    assert result["method"] == "gps" and 0.5 < result["km"] < 0.8
    assert len(result["segments"]) == 2  # Impossible jump never draws a line.


def test_invalid_fix_breaks_route_and_empty_is_explicit():
    base = stamp("2026-09-16T12:00:00+00:00")
    rows=[(base,55,37,None),(base+60,None,None,None),(base+120,55,37.01,None)]
    result=trips.summarize(rows,"2026-09-16","2026-09-16","UTC")
    assert len(result["segments"])==2 and result["km"]==0
    result=trips.summarize([],"2026-09-16","2026-09-16","UTC")
    assert result["samples"]==0 and result["last"] is None


def test_persistence_retention_and_vehicle_isolation(tmp_path):
    async def run():
        async def executor(fn,*args): return fn(*args)
        hass=SimpleNamespace(config=SimpleNamespace(path=lambda *args:str(tmp_path.joinpath(*args))),async_add_executor_job=executor)
        history=trips.TripHistory(hass,"one",30)
        base=stamp("2026-09-16T12:00:00+00:00")
        await history.append(base-40*86400,{"latitude":1,"longitude":1,"odometer":1})
        await history.append(base,{"latitude":"55","longitude":"37","odometer":100})
        await history.append(base+60,{"latitude":55,"longitude":37.01,"odometer":101})
        reopened=trips.TripHistory(hass,"one",30)
        assert (await reopened.query("2026-09-16","2026-09-16","UTC"))["km"]==1
        assert not (await reopened.query("2026-08-01","2026-08-31","UTC"))["samples"]
        assert not (await trips.TripHistory(hass,"two").query("2026-09-16","2026-09-16","UTC"))["samples"]
        await history.append(base+120,{"latitude":"nan","longitude":181,"odometer":-1})
        assert (await history.query("2026-09-16","2026-09-16","UTC"))["samples"]==3
    asyncio.run(run())


def test_history_permission_and_entry_binding():
    node=next(n for n in ast.parse((ROOT/"trips_ws.py").read_text(encoding="utf-8")).body if isinstance(n,ast.AsyncFunctionDef))
    node.decorator_list=[]
    entry=SimpleNamespace(config_entry_id="car",platform="gwm_jolion")
    scope={"DOMAIN":"gwm_jolion","POLICY_READ":"read","er":SimpleNamespace(async_get=lambda hass:SimpleNamespace(async_get=lambda entity:entry))}
    exec(compile(ast.Module(body=[node],type_ignores=[]),"ws","exec"),scope)
    async def run():
        calls=[];errors=[];results=[]
        async def query(*args): calls.append(args);return {"samples":2}
        hass=SimpleNamespace(data={"gwm_jolion":{"car":SimpleNamespace(trip_history=SimpleNamespace(query=query))}},config=SimpleNamespace(time_zone="UTC"))
        connection=SimpleNamespace(user=SimpleNamespace(permissions=SimpleNamespace(check_entity=lambda *args:False)),send_error=lambda *args:errors.append(args),send_result=lambda *args:results.append(args))
        msg={"id":1,"entity_id":"device_tracker.car","start":"2026-09-16","end":"2026-09-16"}
        await scope["get_trips"](hass,connection,msg)
        assert errors[-1][1]=="unauthorized" and not calls
        connection.user.permissions.check_entity=lambda *args:True
        await scope["get_trips"](hass,connection,msg)
        assert calls==[(msg["start"],msg["end"],"UTC")] and results[-1][1]["samples"]==2
        entry.platform="other"
        await scope["get_trips"](hass,connection,msg)
        assert errors[-1][1]=="not_found" and len(calls)==1
        entry.platform="gwm_jolion"
        hass.config.components={"recorder"}
        scope["er"]=SimpleNamespace(async_get=lambda hass:SimpleNamespace(async_get=lambda entity:entry,async_get_entity_id=lambda *args:"sensor.car_odometer"))
        connection.user.permissions.check_entity=lambda entity,*args:entity.startswith("device_tracker.")
        await scope["get_trips"](hass,connection,msg)
        assert errors[-1][1]=="unauthorized" and len(calls)==1
    asyncio.run(run())


def test_archive_only_and_overlap_do_not_double_count():
    base=stamp("2026-09-16T12:00:00+00:00")
    gps=[(base,55,37,None),(base+60,55,37.01,None),(base+120,55,37.02,None)]
    odo=[(base,None,None,100),(base+60,None,None,101),(base+120,None,None,102)]
    result=trips.with_archive([], (gps,odo), "2026-09-16","2026-09-16","UTC")
    assert result["km"]==2 and result["method"]=="odometer" and len(result["segments"][0])==3
    result=trips.with_archive([(base+60,55,37.01,101),(base+120,55,37.02,102)],(gps,odo),"2026-09-16","2026-09-16","UTC")
    assert result["km"]==2 and len(result["segments"][0])==3
    result=trips.with_archive([],([],odo),"2026-09-16","2026-09-16","UTC")
    assert result["km"]==2 and not result["segments"] and result["samples"]==3


def test_recorder_coordinates_attributes_invalid_states_and_miles():
    node=next(n for n in ast.parse((ROOT/"trips_recorder.py").read_text(encoding="utf-8")).body if isinstance(n,ast.FunctionDef))
    scope={"number":trips.number}
    exec(compile(ast.Module(body=[node],type_ignores=[]),"recorder","exec"),scope)
    now=datetime.fromisoformat("2026-09-16T12:00:00+00:00")
    def state(value,attrs):return SimpleNamespace(last_updated=now,state=value,attributes=attrs)
    gps,odo=scope["observations"]({"tracker":[state("not_home",{"latitude":55,"longitude":37}),state("unavailable",{"latitude":55,"longitude":37})],"sensor":[state("100",{"unit_of_measurement":"mi"}),state("unknown",{})]},"tracker","sensor")
    assert gps[0][1:3]==(55,37) and gps[1][1:3]==(None,None)
    assert odo[0][3]==pytest.approx(160.9344) and odo[1][3] is None


def test_recorder_query_keeps_attribute_only_gps_changes():
    node=next(n for n in ast.parse((ROOT/"trips_recorder.py").read_text(encoding="utf-8")).body if isinstance(n,ast.AsyncFunctionDef))
    captured={}
    def history_query(*args,**kwargs):captured.update(kwargs);captured["ids"]=args[3];return {}
    async def executor(job):return job()
    scope={"datetime":datetime,"timezone":timezone,"partial":partial,"period":trips.period,
           "get_instance":lambda hass:SimpleNamespace(async_add_executor_job=executor),
           "history":SimpleNamespace(get_significant_states=history_query),"observations":lambda *args:([],[])}
    exec(compile(ast.Module(body=[node],type_ignores=[]),"recorder_query","exec"),scope)
    result=asyncio.run(scope["read_history"](SimpleNamespace(config=SimpleNamespace(time_zone="UTC")),"device_tracker.car","sensor.car","2026-09-16","2026-09-16"))
    assert result==([],[]) and captured["ids"]==["device_tracker.car","sensor.car"]
    assert not captured["significant_changes_only"] and not captured["no_attributes"] and not captured["minimal_response"]
