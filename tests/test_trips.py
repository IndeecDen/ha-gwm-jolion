"""Calendar, persistence, gaps and authorization of trip history."""
import ast
import asyncio
import logging
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
    assert result["days"][1]["km"] == 2  # Midnight retained; regressing readings ignored.
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
    assert result["gaps"]==[[[55,37],[55,37.01]]]
    result=trips.summarize([],"2026-09-16","2026-09-16","UTC")
    assert result["samples"]==0 and result["last"] is None


def test_movement_speed_thresholds_and_stationary_intervals():
    speed,kind=trips.movement_speed(4/3,60)
    assert speed==pytest.approx(80.0) and kind=="moving"
    speed,kind=trips.movement_speed(11/6,60)
    assert speed==pytest.approx(110.0) and kind=="moving"
    assert trips.movement_speed(0.02,1) == (0.0,"stationary")
    speed,kind=trips.movement_speed(0.1,120)
    assert speed==pytest.approx(3.0) and kind=="moving"
    assert trips.movement_speed(0.1,121)[1] == "stationary"
    assert trips.movement_speed(1,0) == (None,"unknown")


def test_route_speed_metadata_excludes_parking_and_gaps():
    base=stamp("2026-09-16T12:00:00+00:00")
    rows=[(base,55,37,None),(base+60,55.01,37,None),
          (base+120,55.01,37,None),(base+180,55.01,37,None),
          (base+240,55.02,37,None),(base+901,55.03,37,None),
          (base+961,55.04,37,None),(base+1021,None,None,None)]
    result=trips.summarize(rows,"2026-09-16","2026-09-16","UTC")
    assert len(result["segments"])==2
    assert len(result["segment_speeds_kmh"][0])==len(result["segments"][0])-1
    assert result["segment_kinds"][0]==["moving","stationary","stationary","moving"]
    assert result["segment_kinds"][1]==["moving"]
    assert result["segment_speeds_kmh"][0][0]==pytest.approx(66.6,abs=.2)
    assert result["segment_speeds_kmh"][0][1:3]==[0.0,0.0]
    assert result["moving_seconds"]==180
    assert result["days"][0]["moving_seconds"]==180
    assert result["gaps"]


def test_parking_spots_report_start_end_and_ongoing_state():
    base=stamp("2026-09-16T12:00:00+00:00")
    rows=[(base,55,37,None),(base+60,55.01,37,None),
          (base+360,55.01,37,None),(base+660,55.01,37,None),
          (base+720,55.02,37,None),(base+1020,55.02,37,None),
          (base+1320,55.02,37,None)]
    result=trips.summarize(rows,"2026-09-16","2026-09-16","UTC")
    assert result["parking_spots"]==[
        {"latitude":55.01,"longitude":37,"start":base+60,"end":base+660,"duration":600},
        {"latitude":55.02,"longitude":37,"start":base+720,"end":None,"duration":600},
    ]
    assert result["moving_seconds"]==120

    unavailable=[(base,55.03,37,None),(base+300,55.03,37,None),(base+600,55.03,37,None),(base+900,None,None,None)]
    result=trips.summarize(unavailable,"2026-09-16","2026-09-16","UTC")
    assert len(result["parking_spots"])==1 and result["parking_spots"][0]["end"] is None


def test_long_parking_is_not_treated_as_a_missing_gps_gap():
    base=stamp("2026-09-16T12:00:00+00:00")
    rows=[(base,55,37,None),(base+700,55,37,None),(base+760,55.01,37,None)]
    result=trips.summarize(rows,"2026-09-16","2026-09-16","UTC")
    assert len(result["segments"])==1 and not result["gaps"]
    assert result["segment_kinds"]==[["stationary","moving"]]
    assert result["moving_seconds"]==60 and len(result["parking_spots"])==1
    assert result["parking_spots"][0]["end"]==base+700


def test_selected_day_uses_previous_gps_baseline_for_parking():
    base=stamp("2026-09-16T23:50:00+00:00")
    rows=[(base,55,37,None),(base+600,55,37,None),
          (base+900,55,37,None),(base+1200,55.01,37,None)]
    result=trips.summarize(rows,"2026-09-17","2026-09-17","UTC")
    assert result["parking_spots"]==[
        {"latitude":55,"longitude":37,"start":base,"end":base+900,"duration":900}
    ]


def test_parking_continues_across_midnight():
    base=stamp("2026-09-16T23:50:00+00:00")
    rows=[(base,55,37,None),(base+300,55,37,None),
          (base+600,55,37,None),(base+900,55.01,37,None)]
    result=trips.summarize(rows,"2026-09-16","2026-09-17","UTC")
    assert len(result["segments"])==2
    assert result["parking_spots"]==[
        {"latitude":55,"longitude":37,"start":base,"end":base+600,"duration":600}
    ]

    ongoing=rows[:-1]
    result=trips.summarize(ongoing,"2026-09-16","2026-09-17","UTC")
    assert result["parking_spots"][0]["end"] is None

    jumped=[(base,55,37,None),(base+300,55,37,None),(base+600,55.0004,37,None)]
    result=trips.summarize(jumped,"2026-09-16","2026-09-17","UTC")
    assert not result["parking_spots"]


def test_teleport_is_not_reported_as_parking():
    base=stamp("2026-09-16T12:00:00+00:00")
    rows=[(base,55,37,None),(base+300,55,37,None),
          (base+900,55.0004,37,None),(base+1200,55.0008,37,None)]
    result=trips.summarize(rows,"2026-09-16","2026-09-16","UTC")
    assert not result["parking_spots"]
    assert result["moving_seconds"]==0

    jumped=[(base,55,37,None),(base+700,55,37,None),
            (base+1400,55.0004,37,None)]
    result=trips.summarize(jumped,"2026-09-16","2026-09-16","UTC")
    assert not result["parking_spots"] and result["gaps"]
    assert len(result["segments"])==2

    recovered=[(base,55,37,None),(base+300,55,37,None),
               (base+600,None,None,None),(base+900,55.01,37,None)]
    result=trips.summarize(recovered,"2026-09-16","2026-09-16","UTC")
    assert not result["parking_spots"]


def test_route_simplification_preserves_speed_edge_alignment():
    base=stamp("2026-09-16T12:00:00+00:00")
    rows=[(base+index*60,55+index*.001,37,None) for index in range(5002)]
    result=trips.summarize(rows,"2026-09-16","2026-09-20","UTC")
    assert result["simplified"] and len(result["segments"][0])<5002
    for points,speeds,kinds in zip(result["segments"],result["segment_speeds_kmh"],result["segment_kinds"]):
        assert len(speeds)==len(points)-1
        assert len(kinds)==len(points)-1
        assert all(kind=="moving" for kind in kinds)


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


def test_local_query_uses_previous_gps_baseline_for_parking(tmp_path):
    hass=SimpleNamespace(config=SimpleNamespace(path=lambda *args:str(tmp_path.joinpath(*args))))
    history=trips.TripHistory(hass,"car")
    base=stamp("2026-09-16T23:50:00+00:00")
    history._append(base,{"latitude":55,"longitude":37})
    history._append(base+600,{"latitude":55,"longitude":37})
    history._append(base+900,{"latitude":55,"longitude":37})
    history._append(base+1200,{"latitude":55.01,"longitude":37})
    result=history._query("2026-09-17","2026-09-17","UTC")
    assert result["parking_spots"][0]["start"]==base
    assert result["parking_spots"][0]["end"]==base+900


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
    assert result["moving_seconds"]==120 and result["days"][0]["moving_seconds"]==120
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
    def history_query(*args,**kwargs):captured.update(kwargs);captured["ids"]=args[3];captured["start"]=args[1];return {}
    async def executor(job):return job()
    scope={"datetime":datetime,"timezone":timezone,"partial":partial,"period":trips.period,
           "PARKING_BASELINE_SECONDS":trips.PARKING_BASELINE_SECONDS,
           "get_instance":lambda hass:SimpleNamespace(async_add_executor_job=executor),
           "history":SimpleNamespace(get_significant_states=history_query),"observations":lambda *args:([],[])}
    exec(compile(ast.Module(body=[node],type_ignores=[]),"recorder_query","exec"),scope)
    result=asyncio.run(scope["read_history"](SimpleNamespace(config=SimpleNamespace(time_zone="UTC")),"device_tracker.car","sensor.car","2026-09-16","2026-09-16"))
    assert result==([],[]) and captured["ids"]==["device_tracker.car","sensor.car"]
    expected_start=datetime.fromtimestamp(stamp("2026-09-16T00:00:00+00:00")-trips.PARKING_BASELINE_SECONDS,timezone.utc)
    assert captured["start"]==expected_start
    assert not captured["significant_changes_only"] and not captured["no_attributes"] and not captured["minimal_response"]


def test_delayed_odometer_catches_up_across_missing_readings_and_midnight():
    base=stamp("2026-09-16T23:55:00+00:00")
    rows=[(base,55,37,1000),(base+60,None,None,None),(base+300,55,37,1000),
          (base+600,56,38,1084),(base+630,56,38,1000),(base+660,56,38,1084)]
    result=trips.summarize(rows,"2026-09-16","2026-09-17","UTC")
    assert result["km"]==84 and result["days"][1]["km"]==84
    assert result["gaps"]  # The missing road is indicated, not counted as GPS distance.


def test_archive_fills_holes_after_local_capture_started():
    base=stamp("2026-09-16T12:00:00+00:00")
    local=[(base,55,37,100),(base+3600,56,38,184)]
    gps=[(base+1200,55.2,37.2,None),(base+2400,55.5,37.5,None)]
    odo=[(base+1200,None,None,125),(base+2400,None,None,150)]
    result=trips.with_archive(local,(gps,odo),"2026-09-16","2026-09-16","UTC")
    assert result["km"]==84
    assert sum(map(len,result["segments"]))==4


def test_previous_day_baseline_counts_first_morning_trip(tmp_path):
    hass=SimpleNamespace(config=SimpleNamespace(path=lambda *args:str(tmp_path.joinpath(*args))))
    history=trips.TripHistory(hass,"car")
    history._append(stamp("2026-09-15T23:50:00+00:00"),{"odometer":100})
    history._append(stamp("2026-09-16T08:00:00+00:00"),{"odometer":120})
    result=history._query("2026-09-16","2026-09-16","UTC")
    assert result["km"]==20 and result["samples"]==1


def test_slow_recorder_falls_back_to_local_history():
    node=next(n for n in ast.parse((ROOT/"trips_ws.py").read_text(encoding="utf-8")).body if isinstance(n,ast.AsyncFunctionDef))
    node.decorator_list=[]
    class InjectRecorder(ast.NodeTransformer):
        def visit_ImportFrom(self,node):
            return ast.copy_location(ast.Pass(),node)
    node=InjectRecorder().visit(node)
    entry=SimpleNamespace(config_entry_id="car",platform="gwm_jolion")
    registry=SimpleNamespace(async_get=lambda entity:entry,async_get_entity_id=lambda *args:None)
    cancelled=[]
    async def slow(*args):
        try: await asyncio.sleep(100)
        finally: cancelled.append(True)
    scope={"DOMAIN":"gwm_jolion","POLICY_READ":"read","er":SimpleNamespace(async_get=lambda hass:registry),
           "read_history":slow,"asyncio":SimpleNamespace(timeout=lambda seconds:asyncio.timeout(0.01)),"_LOGGER":logging.getLogger(__name__)}
    exec(compile(ast.Module(body=[node],type_ignores=[]),"ws","exec"),scope)
    async def run():
        results=[];errors=[]
        async def query(*args):return {"km":84}
        hass=SimpleNamespace(data={"gwm_jolion":{"car":SimpleNamespace(trip_history=SimpleNamespace(query=query))}},config=SimpleNamespace(time_zone="UTC",components={"recorder"}))
        connection=SimpleNamespace(user=SimpleNamespace(permissions=SimpleNamespace(check_entity=lambda *args:True)),send_error=lambda *args:errors.append(args),send_result=lambda *args:results.append(args))
        await scope["get_trips"](hass,connection,{"id":1,"entity_id":"device_tracker.car","start":"2026-09-16","end":"2026-09-16"})
        assert results==[(1,{"km":84})] and not errors and cancelled
    asyncio.run(run())
