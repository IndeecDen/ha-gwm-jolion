"""Fusion, persistence and HTTP protocol, with a minimal HA runtime adapter."""
import asyncio
import hashlib
import importlib.util
from pathlib import Path
import sys
import time
from types import ModuleType, SimpleNamespace
from unittest.mock import patch
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

ROOT=Path(__file__).resolve().parents[1]/"custom_components/gwm_jolion"
package=ModuleType("locator_test_package");package.__path__=[str(ROOT)]
sys.modules[package.__name__]=package

def load():
    names=["homeassistant","homeassistant.components","homeassistant.components.http","homeassistant.auth","homeassistant.auth.permissions","homeassistant.auth.permissions.const","homeassistant.helpers","homeassistant.helpers.entity_registry","homeassistant.helpers.event"]
    modules={name:ModuleType(name) for name in names}
    modules["homeassistant.components.http"].HomeAssistantView=object
    modules["homeassistant.components.http"].KEY_HASS_USER="test_user"
    modules["homeassistant.auth.permissions.const"].POLICY_READ="read"
    modules["homeassistant.helpers.event"].async_track_time_interval=lambda *a:None
    modules["homeassistant.helpers.entity_registry"].async_get=lambda hass:SimpleNamespace(async_get=lambda eid:SimpleNamespace(config_entry_id="car",platform="gwm_jolion") if eid=="device_tracker.car" else None)
    spec=importlib.util.spec_from_file_location("locator_test_package.locator",ROOT/"locator.py")
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module
    with patch.dict(sys.modules,modules):spec.loader.exec_module(module)
    return module

locator=load()

def test_pairing_admin_validation_and_preserved_options():
    async def run():
        entry=SimpleNamespace(entry_id="car",domain="gwm_jolion",options={"poll_interval":60})
        other=SimpleNamespace(entry_id="other",options={locator.ENABLED:True,locator.VEHICLE_ID:"taken"})
        reloads=[]
        async def reload(eid):reloads.append(eid);return True
        entries=SimpleNamespace(async_get_entry=lambda eid:entry,async_entries=lambda domain:[entry,other],async_update_entry=lambda e,options:setattr(e,"options",options),async_reload=reload)
        view=locator.LocatorPairing(SimpleNamespace(config_entries=entries))
        @web.middleware
        async def auth(request,handler):
            request["test_user"]=SimpleNamespace(is_admin=request.headers.get("Test-Admin")=="yes")
            return await handler(request)
        server=web.Application(middlewares=[auth])
        server.router.add_post('/pair/{entity_id}',lambda r:view.post(r,r.match_info['entity_id']))
        server.router.add_get('/pair/{entity_id}',lambda r:view.get(r,r.match_info['entity_id']))
        async with TestClient(TestServer(server)) as client:
            path='/pair/device_tracker.car'
            good={"vehicle_id":"jolion","upload_key":"a"*48}
            assert (await client.post(path,json=good)).status==403
            headers={"Test-Admin":"yes"}
            assert (await client.post(path,json={**good,"vehicle_id":"taken"},headers=headers)).status==409
            for bad in ({},[],None,{**good,"upload_key":"short"},{**good,"vehicle_id":1}):
                assert (await client.post(path,json=bad,headers=headers)).status==400
            assert (await client.post(path,data='x'*3000,headers=headers)).status==413
            assert (await client.post('/pair/sensor.car',json=good,headers=headers)).status==404
            response=await client.post(path,json=good,headers=headers)
            assert response.status==200 and await response.json()=={"paired":True}
            assert entry.options[locator.KEY_HASH]==hashlib.sha256(good['upload_key'].encode()).hexdigest()
            assert entry.options[locator.ENABLED] and entry.options['poll_interval']==60
            assert entry.options[locator.UPLOAD_KEY]==good['upload_key']
            assert (await client.get(path)).status==403
            stored=await client.get(path,headers=headers)
            assert stored.headers['Cache-Control']=='no-store'
            assert await stored.json()==good
            assert reloads==['car']
    asyncio.run(run())
from locator_test_package.locator_merge import choose_live, fuse, cloud_point
KEY="a"*48
NOW=int(time.time()*1000)

def test_relay_interval_is_clamped_to_the_range_the_app_offers():
    # A hand-edited or corrupted option must never produce a 0 s or negative timer.
    assert locator.relay_interval({})==30
    assert locator.relay_interval({locator.DISK_RELAY_INTERVAL:5})==5
    assert locator.relay_interval({locator.DISK_RELAY_INTERVAL:300})==300
    assert locator.relay_interval({locator.DISK_RELAY_INTERVAL:0})==5
    assert locator.relay_interval({locator.DISK_RELAY_INTERVAL:-60})==5
    assert locator.relay_interval({locator.DISK_RELAY_INTERVAL:9999})==300
    assert locator.relay_interval({locator.DISK_RELAY_INTERVAL:"abc"})==30
    assert locator.relay_interval({locator.DISK_RELAY_INTERVAL:None})==30
    assert locator.relay_interval(None)==30
    # The Android app and the integration must agree on the bounds.
    assert locator.MIN_RELAY_INTERVAL==5 and locator.MAX_RELAY_INTERVAL==300

def app(t=NOW,accuracy=5,**changes):
    return dict(dict(id=f"app-{t}-000000",timestamp_ms=t,latitude=55.75,longitude=37.62,accuracy_m=accuracy,speed_kmh=40,bearing=None,altitude_m=None,source="app",time_known=True,accuracy_known=True),**changes)


def test_restart_after_commit_before_reply_accepts_retry_without_duplicates(tmp_path):
    async def run():
        _, first = make_history(tmp_path)
        await first.initialize()
        points = [app(NOW-5000), app(NOW)]
        # Simulate a committed write whose HTTP response never reaches the app.
        first.app_archive.ingest(points, now_ms=NOW+1000)
        _, restarted = make_history(tmp_path)
        await restarted.initialize()
        assert restarted.last_received_ms == NOW+1000
        assert await restarted.ingest(points) == [p["id"] for p in points]
        with restarted.app_archive.connect() as db:
            assert db.execute("SELECT COUNT(*) FROM points").fetchone()[0] == 2
        assert restarted.last_received_ms == NOW+1000
    asyncio.run(run())

def cloud(t=NOW,**changes):
    return {**cloud_point(t/1000,{"latitude":55.76,"longitude":37.63}),**changes}

def test_cached_cloud_does_not_beat_recent_real_fix():
    a,c=app(NOW-10000),cloud(NOW)
    assert choose_live(a,c,NOW)==a
    assert choose_live(app(NOW-180000),c,NOW)==c
    assert c["accuracy_m"] is None and not c["time_known"]


def test_unified_playback_retains_second_fixes_and_measured_speed(tmp_path):
    from datetime import datetime,UTC
    start=((NOW//86400000)-1)*86400000+3600000
    day=datetime.fromtimestamp(start/1000,UTC).date().isoformat()
    async def run():
        hass,h=make_history(tmp_path);await h.initialize()
        points=[app(start+i*1000,latitude=55.75+i*.0001,speed_kmh=37) for i in range(30010)]
        await h.ingest(points)
        result=await h.query(day,day,'UTC')
        assert len(result['playback'])==30010
        assert result['playback'][1]['timestamp_ms']-result['playback'][0]['timestamp_ms']==1000
        assert all(p['speed_kmh']==37 and not p['speed_estimated'] and p['source']=='app' for p in result['playback'])
        assert result['simplified']
        assert all(speed==37 for segment in result['segment_speeds_kmh'] for speed in segment)
    asyncio.run(run())


def test_long_period_remains_available_without_losing_archived_seconds(tmp_path):
    hass,h=make_history(tmp_path)
    h.app_archive.initialize()
    start=NOW-7*86400000
    with h.app_archive.connect() as db:
        db.executemany('INSERT INTO points (id,timestamp_ms,latitude,longitude,accuracy_m,speed_kmh,bearing,altitude_m,received_ms) VALUES (?,?,?,?,?,?,?,?,?)',((f'long-{i:016}',start+i*1000,55.75,37.62,5,0,None,None,NOW) for i in range(200001)))
    h._append((start+1000)/1000,{'latitude':56,'longitude':38})
    points,_=h._merged(start,start+200001000)
    assert len(points)<100002 and all(p['source']=='app' for p in points)
    assert points[0]['timestamp_ms']==start and points[-1]['timestamp_ms']==start+200000000
    with h.app_archive.connect() as db:
        assert db.execute('SELECT COUNT(*) FROM points').fetchone()[0]==200001


def test_stationary_history_filtered_without_editing_archive(tmp_path):
    from datetime import datetime,UTC
    start=((NOW//86400000)-1)*86400000+3600000
    day=datetime.fromtimestamp(start/1000,UTC).date().isoformat()
    async def run():
        hass,h=make_history(tmp_path);await h.initialize()
        raw=[app(start+i*1000,latitude=55.75+(i%11)*.0002,longitude=37.62+(i%7)*.0003,speed_kmh=0) for i in range(700)]
        await h.ingest(raw)
        result=await h.query(day,day,'UTC')
        assert result['km']==0
        assert len({(p['latitude'],p['longitude']) for p in result['playback']})==1
        assert len(result['playback'])==700
        original=await h.query(day,day,'UTC',raw=True)
        assert len({(p['latitude'],p['longitude']) for p in original['playback']})>1
        assert [(p['latitude'],p['longitude']) for p in original['playback']]==[(p['latitude'],p['longitude']) for p in raw]
        again=await h.query(day,day,'UTC')
        assert again['playback']==result['playback']
        with h.app_archive.connect() as db:
            assert db.execute('SELECT COUNT(DISTINCT latitude) FROM points').fetchone()[0]==11
    asyncio.run(run())


def test_switch_between_cloud_and_phone_has_no_connecting_line():
    from locator_test_package.trips import with_archive
    start=1700000000
    rows=[(start,55,37,None),(start+10,56,38,None)]
    result=with_archive(rows,([],[]),'2023-11-14','2023-11-14','UTC',break_before={(start+10)*1000})
    assert all(len(segment)==1 for segment in result['segments'])
    assert result['gaps']==[]

def test_http_history_does_not_invent_motion_between_sources(tmp_path):
    _,history=make_history(tmp_path)
    history._merged=lambda low,high: ([app(NOW-10000,speed_kmh=0),cloud(NOW,latitude=55.7505,longitude=37.62)],[])
    result=history.card_history(NOW-20000,NOW+1000)
    assert result['distance_km']==0
    assert result['max_speed_kmh']==0
    assert all(len(segment)==1 for segment in result['segments'])

def test_speed_uncertainty_survives_archive_and_affects_only_filtered_view(tmp_path):
    from datetime import datetime,UTC
    start=((NOW//86400000)-1)*86400000+3600000
    day=datetime.fromtimestamp(start/1000,UTC).date().isoformat()
    async def run():
        _,history=make_history(tmp_path);await history.initialize()
        raw=[app(start+i*1000,accuracy=20,latitude=55.75+(i%30)*.6/111195,speed_kmh=8,speed_accuracy_kmh=10) for i in range(180)]
        await history.ingest(raw)
        filtered=await history.query(day,day,'UTC')
        original=await history.query(day,day,'UTC',raw=True)
        assert all(p['speed_kmh']==0 for p in filtered['playback'])
        assert len({p['latitude'] for p in filtered['playback']})==1
        assert all(p['speed_kmh']==8 and p['speed_accuracy_kmh']==10 for p in original['playback'])
        assert len({p['latitude'] for p in original['playback']})==30
    asyncio.run(run())

def test_newer_measured_fix_wins_over_precise_but_old():
    assert choose_live(app(NOW-20000,1),cloud(NOW,time_known=True,accuracy_known=True,accuracy_m=15),NOW)["source"]=="cloud"

def test_same_instant_uses_measured_accuracy_from_either_source():
    a=app(NOW,20);c=cloud(NOW+500,time_known=True,accuracy_known=True,accuracy_m=3)
    assert choose_live(a,c,NOW+1000)==c
    assert fuse([a],[c])==[c]
    assert fuse([app(NOW,1)],[c])==[app(NOW,1)]

def test_history_replaces_overlap_and_keeps_uncovered_cloud():
    a=[app(NOW+i*1000) for i in range(5)]
    c=[cloud(NOW-60000),cloud(NOW+1000),cloud(NOW+90000)]
    merged=fuse(a,c)
    assert len(merged)==7 and sum(p["source"]=="cloud" for p in merged)==2
    assert merged==fuse(list(reversed(a)),list(reversed(c)))

def test_stale_and_future_live_handling():
    assert choose_live(app(NOW-600000),cloud(NOW-300000),NOW)["source"]=="cloud"
    assert choose_live(app(NOW+600000),None,NOW) is None


def test_card_source_selection_isolates_geometry_mileage_and_cache(tmp_path):
    from datetime import datetime, UTC
    async def run():
        _, history = make_history(tmp_path)
        await history.initialize()
        base = NOW-3600000
        day = datetime.fromtimestamp(base/1000,UTC).date().isoformat()
        points = [app(base+i*10000,latitude=55+i*.001) for i in range(3)]
        await history.ingest(points)
        for i in range(3):
            history._append(base/1000+i*10,{'latitude':56+i*.001,'longitude':38,'odometer':100+i})
        # One mirrored app row outside cloud observation timestamps.
        await history.ingest([app(base+5000,latitude=55.0005)])
        only_app = await history.query(day,day,'UTC',include_cloud=False)
        only_cloud = await history.query(day,day,'UTC',include_app=False)
        assert only_app['source_counts']['cloud']==0 and only_app['source_counts']['app']==4
        # GPS source selection must not disable the independent Recorder odometer.
        assert only_app['method']=='odometer' and only_app['km']==2
        assert only_cloud['source_counts']['app']==0 and only_cloud['source_counts']['cloud']==3
        assert all(p[0]>=56 for segment in only_cloud['segments'] for p in segment)
        assert only_cloud['km']==2
        cached = await history.query(day,day,'UTC',include_cloud=False)
        assert cached['source_counts']==only_app['source_counts']
        assert cached['history_profile']['cache']=='hit'
        archive=([(base/1000+25,54,36,None)],[])
        isolated=await history.query(day,day,'UTC',archive,include_app=False)
        assert all(p[0]>=56 for segment in isolated['segments'] for p in segment)
        empty=await history.query(day,day,'UTC',include_app=False,include_cloud=False)
        assert empty['samples']==0 and not empty['parking_spots'] and not empty['segments']
        history.enabled=False
        empty=await history.query(day,day,'UTC',include_cloud=False,raw=True)
        assert empty['samples']==0
    asyncio.run(run())

def make_history(tmp_path):
    async def executor(fn,*args):return await asyncio.to_thread(fn,*args)
    hass=SimpleNamespace(data={"gwm_jolion":{}},config=SimpleNamespace(path=lambda *p:str(tmp_path.joinpath(*p))),async_add_executor_job=executor)
    entry=SimpleNamespace(entry_id="car",options={locator.ENABLED:True,locator.VEHICLE_ID:"jolion",locator.KEY_HASH:hashlib.sha256(KEY.encode()).hexdigest()})
    history=locator.HybridHistory(hass,entry,90)
    hass.data["gwm_jolion"]["car"]=SimpleNamespace(trip_history=history)
    return hass,history

def test_late_ingest_durable_and_no_live_rewind(tmp_path):
    async def run():
        hass,h=make_history(tmp_path);await h.initialize()
        await h.ingest([app(NOW)])
        await h.append((NOW-300000)/1000,{"latitude":56,"longitude":38})
        await h.ingest([app(NOW-300000,2)])
        assert h.latest["timestamp_ms"]==NOW
        await h.ingest([app(NOW-300000,2)])
        data=h.card_history(NOW-400000,NOW+1000)
        assert data["total_points"]==2 and data["source_counts"]=={"app":2,"cloud":0}
        restored=locator.HybridHistory(hass,h.entry,90);await restored.initialize()
        assert restored.latest["timestamp_ms"]==NOW
    asyncio.run(run())

def test_cloud_only_distance_is_estimated_and_accuracy_unknown(tmp_path):
    async def run():
        _,h=make_history(tmp_path);await h.initialize()
        for i in range(3):await h.append((NOW+i*10000)/1000,{"latitude":55.75,"longitude":37.62+i*.001})
        data=h.card_history(NOW,NOW+30000)
        assert data["distance_km"]>0 and data["source_counts"]["cloud"]==3
        assert data["points"][1]["speed_estimated"] and data["points"][0]["accuracy_m"] is None
    asyncio.run(run())

def test_disable_reverts_without_erasing_app_archive(tmp_path):
    async def run():
        _,h=make_history(tmp_path);await h.initialize();await h.ingest([app(NOW)])
        await h.append((NOW-10000)/1000,{"latitude":56,"longitude":38})
        h.enabled=False
        assert h.latest["source"]=="cloud" and h.card_history(NOW-20000,NOW+1)["source_counts"]["app"]==0
        h.enabled=True;assert h.latest["source"]=="app"
    asyncio.run(run())

def test_best_accuracy_at_same_app_timestamp_and_cloud_parking(tmp_path):
    async def run():
        _,h=make_history(tmp_path);await h.initialize()
        await h.ingest([app(NOW,30,id='app-worse-0000001'),app(NOW,2,id='app-better-000001')])
        assert h.latest['accuracy_m']==2
        for i in range(12):
            await h.append((NOW-3600000+i*60000)/1000,{'latitude':55.75,'longitude':37.62,'odometer':1234})
        result=h.card_history(NOW-3700000,NOW-2800000)
        assert result['stops'] and result['stops'][0]['estimated']
    asyncio.run(run())

def test_options_validate_pairing_preserve_key_and_unrelated_options():
    import re
    import voluptuous as vol
    from test_stability import methods
    from locator_test_package import const
    scope={k:getattr(const,k) for k in dir(const) if k.isupper()}
    scope.update(__name__="locator_test_package.config_flow",__package__="locator_test_package",hashlib=hashlib,re=re,vol=vol,LOCATOR_ENABLED=locator.ENABLED,LOCATOR_ID=locator.VEHICLE_ID,LOCATOR_KEY=locator.UPLOAD_KEY,LOCATOR_HASH=locator.KEY_HASH,
                 TOKEN=locator.DISK_OAUTH,FOLDER=locator.DISK_FOLDER,CLEANUP=locator.DISK_CLEANUP,CLEANUP_GRACE_HOURS=locator.DISK_CLEANUP_GRACE_HOURS,DEFAULT_DISK_FOLDER=locator.DEFAULT_DISK_FOLDER,
                 DISK_RELAY_INTERVAL=locator.DISK_RELAY_INTERVAL,DEFAULT_RELAY_INTERVAL=locator.DEFAULT_RELAY_INTERVAL,MIN_RELAY_INTERVAL=locator.MIN_RELAY_INTERVAL,MAX_RELAY_INTERVAL=locator.MAX_RELAY_INTERVAL,
                 CONF_PROTOCOL_CAPTURE='protocol_capture_enabled',DEFAULT_PROTOCOL_CAPTURE=False,CLEAR_SECURITY_PIN='clear_security_pin',MANUAL_CAPABILITY_OPTIONS={},resolve_manual_capabilities=lambda options:{},GPS_INTERVAL_SELECTOR=int,POLL_INTERVAL_SELECTOR=int,
                 selector=SimpleNamespace(TextSelector=lambda x:x,TextSelectorConfig=lambda **k:str,TextSelectorType=SimpleNamespace(PASSWORD='password')))
    method=methods('config_flow.py','GwmJolionOptionsFlow',['async_step_init'],scope)['async_step_init']
    async def run():
        saved={locator.KEY_HASH:hashlib.sha256(KEY.encode()).hexdigest(),'custom_preference':42}
        entry=SimpleNamespace(entry_id='car',options=saved,data={})
        others=[]
        flow=SimpleNamespace(config_entry=entry,hass=SimpleNamespace(config_entries=SimpleNamespace(async_entries=lambda domain:others)),async_create_entry=lambda **kw:dict(type='create',**kw),async_show_form=lambda **kw:dict(type='form',**kw))
        form=await method(flow)
        assert form['description_placeholders']['locator_url']=='/gwm-jolion-pairing?entry_id=car'
        paired=await method(flow,{locator.ENABLED:True,locator.VEHICLE_ID:'remembered',locator.UPLOAD_KEY:KEY})
        entry.options=paired['data']
        reopened=await method(flow)
        defaults={marker.schema:marker.default() for marker in reopened['data_schema'].schema if marker.schema in (locator.VEHICLE_ID,locator.UPLOAD_KEY)}
        assert defaults=={locator.VEHICLE_ID:'remembered',locator.UPLOAD_KEY:KEY}
        disk=await method(flow,{locator.ENABLED:True,locator.VEHICLE_ID:'remembered',locator.UPLOAD_KEY:KEY,'golion_locator_transport':'yandex_disk','golion_locator_yandex_public_url':'https://disk.yandex.ru/d/test'})
        assert disk['type']=='create' and disk['data']['golion_locator_transport']=='yandex_disk'
        invalid=await method(flow,{locator.ENABLED:True,locator.UPLOAD_KEY:KEY,'golion_locator_transport':'yandex_disk','golion_locator_yandex_public_url':'http://localhost/private'})
        assert invalid['errors']['golion_locator_yandex_public_url']=='invalid_yandex_url'
        entry.options=saved
        result=await method(flow,{locator.ENABLED:True,locator.VEHICLE_ID:'jolion'})
        assert result['type']=='create' and result['data'][locator.KEY_HASH]==saved[locator.KEY_HASH]
        assert result['data']['custom_preference']==42
        others.append(SimpleNamespace(entry_id='another',options={locator.ENABLED:True,locator.VEHICLE_ID:'jolion'}))
        result=await method(flow,{locator.ENABLED:True,locator.VEHICLE_ID:'jolion'})
        assert result['errors'][locator.VEHICLE_ID]=='duplicate_locator_id'
        result=await method(flow,{locator.ENABLED:True,locator.VEHICLE_ID:'mycar',locator.UPLOAD_KEY:'short'})
        assert result['errors'][locator.UPLOAD_KEY]=='invalid_locator_key'
        result=await method(flow,{locator.ENABLED:False})
        assert result['type']=='create' and not result['data'][locator.ENABLED]
    asyncio.run(run())

def test_http_auth_disable_retry_permissions_disk_failure(tmp_path):
    async def run():
        hass,h=make_history(tmp_path);await h.initialize()
        upload=locator.LocatorUpload(hass);read=locator.LocatorHistory(hass)
        async def post(r):return await upload.post(r,r.match_info["vehicle"])
        async def get(r):
            r["test_user"]=SimpleNamespace(permissions=SimpleNamespace(check_entity=lambda *a:r.headers.get("Test-Read")=="yes"))
            return await read.get(r,r.match_info["entity"])
        server=web.Application();server.router.add_post('/api/jolion_locator/v1/{vehicle}',post);server.router.add_get('/api/gwm_jolion/locator/{entity}',get)
        async with TestClient(TestServer(server)) as client:
            path='/api/jolion_locator/v1/jolion';headers={"X-Jolion-Key":KEY};payload={"version":1,"points":[app()]}
            assert (await client.post(path,json=payload)).status==401
            for _ in range(2):
                reply=await client.post(path,json=payload,headers=headers)
                assert reply.status==200 and (await reply.json())["ack"]==[app()["id"]]
            assert h.card_history(NOW-1,NOW+1)["total_points"]==1
            h.enabled=False;assert (await client.post(path,json=payload,headers=headers)).status==401
            h.enabled=True
            assert (await client.post(path,data='x'*262145,headers=headers)).status==413
            assert (await client.post(path,data='{',headers=headers)).status==400
            with patch.object(h.app_archive,"ingest",side_effect=OSError("test disk full")):
                reply=await client.post(path,json=payload,headers=headers)
                assert reply.status==503 and 'ack' not in await reply.json()
            url=f'/api/gwm_jolion/locator/device_tracker.car?start_ms={NOW-1}&end_ms={NOW+1}'
            assert (await client.get(url)).status==403
            reply=await client.get(url,headers={"Test-Read":"yes"})
            assert reply.status==200 and (await reply.json())["source_counts"]["app"]==1
            assert (await client.post('/api/jolion_locator/v1/other',json=payload,headers=headers)).status==401
    asyncio.run(run())


def test_speed_accuracy_validation_storage_and_legacy_migration(tmp_path):
    import sqlite3
    from locator_test_package.locator_protocol import Archive,validate
    import pytest
    path=tmp_path/'legacy.sqlite'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE points (id TEXT PRIMARY KEY,timestamp_ms INTEGER NOT NULL,latitude REAL NOT NULL,longitude REAL NOT NULL,accuracy_m REAL NOT NULL,speed_kmh REAL,bearing REAL,altitude_m REAL,received_ms INTEGER NOT NULL)')
        db.execute('INSERT INTO points VALUES (?,?,?,?,?,?,?,?,?)',('legacy-point-00001',NOW,55,37,5,0,None,None,NOW))
    archive=Archive(path);archive.initialize()
    assert archive.latest()['speed_accuracy_kmh'] is None
    row=app(NOW+1000,speed_accuracy_kmh=1.8)
    validated=validate(dict(version=1,points=[row]),NOW)
    archive.ingest(validated)
    assert archive.latest()['speed_accuracy_kmh']==1.8
    archive.ingest(validated)
    with archive.connect() as db:assert db.execute('SELECT COUNT(*) FROM points').fetchone()[0]==2
    for bad in (-1,True,float('nan'),float('inf')):
        with pytest.raises(ValueError):validate(dict(version=1,points=[dict(row,speed_accuracy_kmh=bad)]),NOW)
