"""Optional head-unit input and fused history inside the GWM integration."""
import asyncio
from datetime import datetime, UTC
import hashlib
import hmac
import json
import logging
import math
import re
import time
from time import perf_counter

from aiohttp import web
from homeassistant.components.http import HomeAssistantView, KEY_HASS_USER
from homeassistant.auth.permissions.const import POLICY_READ
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN
from .locator_merge import cloud_point, choose_live, fuse
from .locator_protocol import Archive, validate, analyze, distance
from .trips import TripHistory, period, with_archive, summarize, playback
from .locator_filter import filter_display

_LOGGER = logging.getLogger(__name__)
ENABLED = "golion_locator_enabled"
VEHICLE_ID = "golion_locator_vehicle_id"
KEY_HASH = "golion_locator_key_hash"
UPLOAD_KEY = "golion_locator_upload_key"
MAX_BODY = 262144


def merge_inferred_parking(spots, points, mileage):
    """Add parking that spans a transmission gap to the card's stop list.

    The card reads `parking_spots`, which the observation-based algorithm cannot
    produce across a silence: a sleeping car has no observations at all. Anything
    the odometer proves is added, and anything an existing spot already covers is
    left alone so one parking never gets two letters.
    """
    # Mileage timestamps are seconds; analyze() looks up milliseconds.
    odometers={int(mile[0]*1000):mile[3] for mile in mileage if mile[3] is not None}
    analysis=analyze(points, odometers)
    inferred=[s for s in analysis['stops'] if s.get('inferred')]
    if not inferred:
        return spots
    existing=[s for s in spots if s.get('end') is not None]
    added=[]
    for stop in inferred:
        start=stop['start_ms']/1000
        end=stop['end_ms']/1000
        # A spot that already covers this interval represents the same parking.
        if any(other['end']>=start and other['start']<=end for other in existing):
            continue
        added.append({"latitude":stop['latitude'],"longitude":stop['longitude'],
                      "start":start,"end":end,"observed_until":end,
                      "duration":stop['duration_s'],"inferred":True,
                      "inferred_by":stop.get('inferred_by')})
        existing.append(added[-1])
    return sorted([*spots,*added],key=lambda s:s['start'])
# Imported from locator_yandex lazily below; names here keep the option keys visible.
DISK_OAUTH = "golion_locator_disk_oauth"
DISK_FOLDER = "golion_locator_disk_folder"
DISK_CLEANUP = "golion_locator_disk_cleanup"
DISK_CLEANUP_GRACE_HOURS = "golion_locator_disk_cleanup_grace_hours"
DISK_RELAY_INTERVAL = "golion_locator_relay_interval"
DEFAULT_DISK_FOLDER = "/JolionLocator"
# Matches Config.MIN_INTERVAL_SECONDS / MAX_INTERVAL_SECONDS in the Android app.
MIN_RELAY_INTERVAL = 5
MAX_RELAY_INTERVAL = 300
DEFAULT_RELAY_INTERVAL = 30
# A parking that is still running when the requested day begins has to be able to
# look back far enough to find where it started. One full night plus a margin.
OVERNIGHT_BASELINE_MS = 18 * 3600 * 1000


def relay_interval(options) -> int:
    """How often the Disk folder is polled, in seconds, clamped to a safe range."""
    try:
        value = int((options or {}).get(DISK_RELAY_INTERVAL, DEFAULT_RELAY_INTERVAL))
    except (TypeError, ValueError):
        return DEFAULT_RELAY_INTERVAL
    return max(MIN_RELAY_INTERVAL, min(MAX_RELAY_INTERVAL, value))


class HybridHistory(TripHistory):
    """Preserve the existing cloud/odometer database; keep acknowledged app fixes separately."""
    def __init__(self, hass, entry, retention):
        super().__init__(hass, entry.entry_id, retention)
        self.entry = entry
        self.enabled = bool(entry.options.get(ENABLED))
        self.app_archive = Archive(hass.config.path(".storage", f"gwm_jolion_{entry.entry_id}_locator.sqlite"))
        self.app_latest = None
        self.last_received_ms = None
        self.cloud_latest = None
        self.gps = None
        self.last_prune = 0
        self.relay = None
        self._query_cache = {}
        self._cache_revision = 0
        self._query_inflight = {}

    def _connect(self):
        """Keep the cloud observation store in the existing trip-history database."""
        return self._cloud_connect()

    def _trip_connect(self):
        from .trips import TripHistory as LocalTripHistory
        return LocalTripHistory._connect(self)

    def _cloud_connect(self):
        import sqlite3
        from pathlib import Path
        path = Path(self.hass.config.path(".storage", f"gwm_jolion_{self.entry.entry_id}_trips.sqlite"))
        path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(path, timeout=10)
        db.execute("CREATE TABLE IF NOT EXISTS points (ts REAL PRIMARY KEY, lat REAL, lon REAL, odo REAL)")
        return db

    def _append(self, stamp, location):
        from .trips import number
        lat, lon, odo = (number(location.get(key)) for key in ("latitude", "longitude", "odometer"))
        if lat is None or lon is None or not -90 <= lat <= 90 or not -180 <= lon <= 180 or (lat == 0 and lon == 0):
            lat = lon = None
        if odo is not None and odo < 0:
            odo = None
        db = self._cloud_connect()
        try:
            db.execute("INSERT OR REPLACE INTO points VALUES (?, ?, ?, ?)", (stamp, lat, lon, odo))
            db.execute("DELETE FROM points WHERE ts < ?", (stamp-self.retention*86400,))
            db.commit()
        finally:
            db.close()

    @property
    def enabled(self):
        return getattr(self, "_hybrid_enabled", False)

    @enabled.setter
    def enabled(self, value):
        self._hybrid_enabled = bool(value)

    async def initialize(self):
        await self.hass.async_add_executor_job(self.app_archive.initialize)
        self.app_latest = await self.hass.async_add_executor_job(self._app_latest)
        self.last_received_ms = await self.hass.async_add_executor_job(self.app_archive.latest_received_ms)
        self.cloud_latest = await self.hass.async_add_executor_job(self._cloud_latest)
        if self.entry.options.get('golion_locator_transport')=='yandex_disk':
            from homeassistant.helpers.aiohttp_client import async_get_clientsession
            from .locator_yandex import PublicDiskRelay
            self.relay=PublicDiskRelay(self,async_get_clientsession(self.hass),self.entry.options.get('golion_locator_yandex_public_url',''),self.entry.options.get(UPLOAD_KEY,''),self.entry.options.get(VEHICLE_ID,'jolion'),token=self.entry.options.get(DISK_OAUTH,''),folder=self.entry.options.get(DISK_FOLDER,DEFAULT_DISK_FOLDER),cleanup=bool(self.entry.options.get(DISK_CLEANUP,False)),grace_hours=self.entry.options.get(DISK_CLEANUP_GRACE_HOURS,24))

    def _app_latest(self):
        point = self.app_archive.latest()
        return {**point, "source": "app", "time_known": True, "accuracy_known": True} if point else None

    def _cloud_latest(self):
        db = self._cloud_connect()
        try:
            row = db.execute("SELECT ts,lat,lon FROM points WHERE lat IS NOT NULL AND lon IS NOT NULL ORDER BY ts DESC LIMIT 1").fetchone()
        finally:
            db.close()
        return cloud_point(row[0], {"latitude": row[1], "longitude": row[2]}) if row else None

    async def append(self, stamp, location):
        await self.hass.async_add_executor_job(self._append, stamp, location)
        self._cache_revision += 1
        point = cloud_point(stamp, location)
        if point and (not self.cloud_latest or point["timestamp_ms"] >= self.cloud_latest["timestamp_ms"]):
            self.cloud_latest = point

    @property
    def latest(self):
        return choose_live(self.app_latest, self.cloud_latest, int(time.time()*1000)) if self.enabled else self.cloud_latest

    def location(self, fallback=None):
        p = self.latest
        if not p:
            return fallback or {}
        return {"latitude": p["latitude"], "longitude": p["longitude"], "gps_accuracy": p.get("accuracy_m"),
                "gps_timestamp_ms": p["timestamp_ms"], "source": p["source"], "time_known": p["time_known"],
                "accuracy_known": p["accuracy_known"], "speed_kmh": p.get("speed_kmh"), "speed_accuracy_kmh": p.get("speed_accuracy_kmh"), "bearing": p.get("bearing")}

    def publish(self):
        if self.gps:
            self.gps.async_set_updated_data({**(self.gps.data or self.gps.parent.data or {}), "location": self.location()})

    async def ingest(self, points):
        async with self.lock:
            ack = await self.hass.async_add_executor_job(self.app_archive.ingest, points)
            self.last_received_ms = await self.hass.async_add_executor_job(self.app_archive.latest_received_ms)
            self.app_latest = await self.hass.async_add_executor_job(self._app_latest)
            await self.hass.async_add_executor_job(self._mirror_app_fixes, points)
            self._cache_revision += 1
        self.publish()
        return ack

    def _mirror_app_fixes(self, points):
        db = self._trip_connect()
        try:
            db.executemany("INSERT OR REPLACE INTO points VALUES (?, ?, ?, ?)",
                           [(p["timestamp_ms"]/1000,p["latitude"],p["longitude"],None) for p in points])
            db.commit()
        finally:
            db.close()

    async def tick(self, now):
        if self.relay:await self.relay.poll()
        self.publish()
        if time.time()-self.last_prune > 86400:
            async with self.lock:
                await self.hass.async_add_executor_job(self.app_archive.prune, self.retention)
                self.app_latest = await self.hass.async_add_executor_job(self._app_latest)
            self.last_prune = time.time()

    def _merged(self, low_ms, high_ms, archive=None):
        with self.app_archive.connect() as db:
            count = db.execute("SELECT COUNT(*) FROM points WHERE timestamp_ms>=? AND timestamp_ms<?", (low_ms-30000, high_ms+30000)).fetchone()[0]
            sample_step=max(1,math.ceil(count/100000)) if count>200000 else 1
            if sample_step==1:
                rows = db.execute("SELECT * FROM points WHERE timestamp_ms>=? AND timestamp_ms<? ORDER BY timestamp_ms", (low_ms-30000, high_ms+30000)).fetchall()
            else:
                rows = db.execute("SELECT * FROM (SELECT *, ROW_NUMBER() OVER (ORDER BY timestamp_ms) AS rn FROM points WHERE timestamp_ms>=? AND timestamp_ms<?) WHERE (rn-1)%?=0 OR rn=? ORDER BY timestamp_ms",(low_ms-30000,high_ms+30000,sample_step,count)).fetchall()
        app = [{**dict(p), "source": "app", "time_known": True, "accuracy_known": True, "sample_step":sample_step} for p in rows] if self.enabled else []
        db = self._connect()
        try:
            rows = db.execute("SELECT ts,lat,lon,odo FROM points WHERE ts>=? AND ts<? ORDER BY ts", ((low_ms-30000)/1000,(high_ms+30000)/1000)).fetchall()
        finally:
            db.close()
        raw_cloud = [*(archive[0] if archive else []), *rows]
        cloud = {}
        for r in raw_cloud:
            p = cloud_point(r[0], {"latitude": r[1], "longitude": r[2]})
            if p:
                cloud[p["timestamp_ms"]] = p
        if sample_step>1 and self.enabled:
            # Sampling for a long calendar period must not let low-quality cloud
            # observations replace the original app fixes omitted from rendering.
            with self.app_archive.connect() as db:
                cloud={t:p for t,p in cloud.items() if not db.execute('SELECT 1 FROM points WHERE timestamp_ms BETWEEN ? AND ? LIMIT 1',(t-30000,t+30000)).fetchone()}
        merged = fuse(app, list(cloud.values()))
        # Everything fetched is returned. A caller asks for a window wider than the
        # day it draws, and summarize() reads PARKING_BASELINE_SECONDS back to keep
        # a parking that began the day before. Clipping here dropped exactly those
        # rows, so each morning the card started a fresh marker at 00:00.
        return merged, rows

    def _query(self, start, end, zone, archive=None, raw=False):
        if not self.enabled:
            return TripHistory._query(self,start,end,zone,archive,raw)
        profile={}
        phase=perf_counter()
        low, high = period(start,end,zone)
        points, rows = self._merged(int(low*1000) - OVERNIGHT_BASELINE_MS, int(high*1000), archive)
        profile["fetch_merge_ms"]=round((perf_counter()-phase)*1000)
        phase=perf_counter()
        points = [dict(p,display_break=f.get("display_break",False)) for p,f in zip(points,filter_display(points))] if raw else filter_display(points)
        profile["filter_ms"]=round((perf_counter()-phase)*1000)
        route = [(p["timestamp_ms"]/1000,p["latitude"],p["longitude"],None) for p in points]
        mileage = [(r[0],None,None,r[3]) for r in rows if r[3] is not None]
        measured={p['timestamp_ms']:p['speed_kmh'] for p in points if p['source']=='app' and p.get('speed_kmh') is not None}
        breaks={p['timestamp_ms'] for p in points if p.get('display_break')}
        phase=perf_counter()
        result = with_archive(route, ([], mileage), start, end, zone, measured_speeds=measured, break_before=breaks)
        result['parking_spots'] = merge_inferred_parking(result.get('parking_spots') or [], points, mileage)
        profile["route_stops_ms"]=round((perf_counter()-phase)*1000)
        shown=[p for p in points if low <= p["timestamp_ms"]/1000 < high]
        result.update(retention_days=self.retention, locator_enabled=True,
                      source_counts={s:sum(p["source"]==s for p in shown) for s in ("app","cloud")},
                      playback_sample_step=max((p.get("sample_step",1) for p in shown),default=1))
        phase=perf_counter()
        result["playback"]=playback(shown)
        profile["playback_ms"]=round((perf_counter()-phase)*1000)
        result["history_profile"]={**profile,"points":len(points),"cache":"miss"}
        return result

    async def query(self, start, end, zone, archive=None, raw=False):
        key=(start,end,zone,raw,self._cache_revision,archive is not None)
        now=time.monotonic()
        if archive is None:
            cached=self._query_cache.get(key)
            if cached and now-cached[0]<30:
                result=dict(cached[1])
                result["history_profile"]={"cache":"hit","cache_lookup_ms":0,"points":cached[2]}
                return result
        task=self._query_inflight.get(key)
        if task is None:
            async def run_query():
                async with self.lock:
                    result=await self.hass.async_add_executor_job(self._query,start,end,zone,archive,raw)
                    if archive is None:
                        self._query_cache[key]=(time.monotonic(),result,len(result.get("playback",())))
                    return result
            task=asyncio.create_task(run_query())
            self._query_inflight[key]=task
        try:
            result=await asyncio.shield(task)
            return dict(result)
        finally:
            if task.done() and self._query_inflight.get(key) is task:
                self._query_inflight.pop(key,None)

    def _prepared(self, low_ms, high_ms):
        """Points the analyser accepts: unusable accuracy parked at infinity, cloud
        speed derived from the positions when the receiver reports none."""
        points, rows = self._merged(low_ms, high_ms)
        points = filter_display(points)
        analysis_points = [{**p, "accuracy_m": p["accuracy_m"] if p.get("accuracy_known") else 1e9} for p in points]
        for i,p in enumerate(analysis_points):
            if p["speed_kmh"] is None and i and not p.get('display_break') and p['source']==analysis_points[i-1]['source']:
                previous = analysis_points[i-1]
                delta = (p["timestamp_ms"]-previous["timestamp_ms"])/1000
                if 0 < delta <= 120:
                    speed = distance(previous,p)/delta*3.6
                    if speed <= 250:
                        p["speed_kmh"] = speed
                        points[i] = {**points[i], "speed_kmh": speed, "speed_estimated": True}
        return points, analysis_points, rows

    def card_history(self, low_ms, high_ms):
        points, analysis_points, rows = self._prepared(low_ms, high_ms)
        # Cloud odometer readings decide whether a transmission gap means the car
        # slept where it stood or really moved.
        odometers={int(r[0]*1000):r[3] for r in rows if r[3] is not None}
        analysis = analyze(analysis_points, odometers)
        # A car left parked overnight must not restart its stop at midnight. Read a
        # day of earlier observations so a parking that is still running keeps the
        # start it really had, while the route and the mileage stay inside the
        # requested window.
        try:
            _, earlier, _ = self._prepared(low_ms - OVERNIGHT_BASELINE_MS, low_ms)
        except Exception:
            earlier = []
        if earlier:
            carried = analyze([*earlier, *analysis_points], odometers)["stops"]
            analysis["stops"] = [stop for stop in carried if stop["end_ms"] >= low_ms]
        # Include cloud-only travel as an explicitly approximate GPS distance.
        estimated_km = 0
        for a,b in zip(points,points[1:]):
            if b.get('display_break') or a['source']!=b['source']:
                continue
            if a["source"]==b["source"]=="app":
                continue
            delta=(b["timestamp_ms"]-a["timestamp_ms"])/1000
            meters=distance(a,b)
            if 0<delta<=120 and 3<meters/delta*3.6<=250 and meters>30:
                estimated_km += meters/1000
        analysis["distance_km"] = round(analysis["distance_km"]+estimated_km,2)
        # Cloud parking remains an estimate from observations, using the existing
        # odometer-aware algorithm. Never splice it across an app-covered interval.
        first=datetime.fromtimestamp(low_ms/1000,UTC).date().isoformat()
        last=datetime.fromtimestamp((high_ms-1)/1000,UTC).date().isoformat()
        groups=[];group=[]
        for p in points:
            if p["source"]=="cloud":
                group.append((p["timestamp_ms"]/1000,p["latitude"],p["longitude"],odometers.get(p["timestamp_ms"])))
            elif group:
                groups.append(group);group=[]
        if group: groups.append(group)
        for group in groups:
            for stop in summarize(group,first,last,"UTC")["parking_spots"]:
                end=stop.get("end") or stop.get("observed_until") or stop["start"]+stop["duration"]
                analysis["stops"].append({"start_ms":int(stop["start"]*1000),"end_ms":int(end*1000),"duration_s":stop["duration"],"latitude":stop["latitude"],"longitude":stop["longitude"],"estimated":True})
        analysis["stops"].sort(key=lambda s:s["start_ms"])
        step = max(1,math.ceil(len(points)/5000))
        shown = points[::step]
        if points and shown[-1] != points[-1]:
            shown.append(points[-1])
        analysis["segments"] = [s[::step]+([s[-1]] if len(s)>1 and (len(s)-1)%step else []) for s in analysis["segments"]]
        return {**analysis, "points":shown, "total_points":len(points), "sample_step":step,
                "source_counts":{s:sum(p["source"]==s for p in points) for s in ("app","cloud")}, "retention_days":self.retention}


def register(hass):
    if not hass.data[DOMAIN].get("_locator_http"):
        hass.http.register_view(LocatorUpload(hass))
        hass.http.register_view(LocatorPairing(hass))
        hass.http.register_view(LocatorHistory(hass))
        hass.data[DOMAIN]["_locator_http"] = True


class LocatorHistory(HomeAssistantView):
    url = "/api/gwm_jolion/locator/{entity_id}"
    name = "api:gwm_jolion:locator_history"
    requires_auth = True

    def __init__(self, hass): self.hass = hass

    async def get(self, request, entity_id):
        if not request[KEY_HASS_USER].permissions.check_entity(entity_id, POLICY_READ):
            return web.json_response({"error":"forbidden"}, status=403)
        registry_entry = er.async_get(self.hass).async_get(entity_id)
        parent = self.hass.data[DOMAIN].get(registry_entry.config_entry_id) if registry_entry else None
        history = getattr(parent, "trip_history", None)
        if not isinstance(history, HybridHistory) or not history.enabled:
            return web.json_response({"error":"disabled"}, status=404)
        try:
            low, high = int(request.query["start_ms"]), int(request.query["end_ms"])
            if low < 0 or not 0 < high-low <= 25*3600000:
                raise ValueError
            data = await self.hass.async_add_executor_job(history.card_history, low, high)
        except (KeyError, ValueError):
            return web.json_response({"error":"invalid_interval"}, status=400)
        data["latest"] = history.latest
        return web.json_response(data, headers={"Cache-Control":"no-store"})


class LocatorPairing(HomeAssistantView):
    url = "/api/gwm_jolion/locator_pairing/{entity_id}"
    name = "api:gwm_jolion:locator_pairing"
    requires_auth = True

    def __init__(self, hass): self.hass = hass

    async def get(self, request, entity_id):
        if not request[KEY_HASS_USER].is_admin:
            return web.json_response({"error":"forbidden"},status=403)
        registry_entry=er.async_get(self.hass).async_get(entity_id)
        entry=self.hass.config_entries.async_get_entry(registry_entry.config_entry_id) if registry_entry and registry_entry.platform==DOMAIN and entity_id.startswith('device_tracker.') else None
        if not entry or entry.domain!=DOMAIN:
            return web.json_response({"error":"not_found"},status=404)
        return web.json_response({"vehicle_id":entry.options.get(VEHICLE_ID,'jolion'),"upload_key":entry.options.get(UPLOAD_KEY,'')},headers={"Cache-Control":"no-store"})

    async def post(self, request, entity_id):
        if not request[KEY_HASS_USER].is_admin:
            return web.json_response({"error":"forbidden"}, status=403)
        registry_entry = er.async_get(self.hass).async_get(entity_id)
        entry = self.hass.config_entries.async_get_entry(registry_entry.config_entry_id) if registry_entry and registry_entry.platform == DOMAIN and entity_id.startswith("device_tracker.") else None
        if entry is None or entry.domain != DOMAIN:
            return web.json_response({"error":"not_found"}, status=404)
        body = bytearray()
        async for chunk in request.content.iter_chunked(1024):
            body.extend(chunk)
            if len(body) > 2048:
                return web.json_response({"error":"payload_too_large"}, status=413)
        try:
            data = json.loads(body)
            vehicle, key = data["vehicle_id"], data["upload_key"]
            if not isinstance(vehicle,str) or not re.fullmatch(r"[a-z0-9_-]{1,40}",vehicle): raise ValueError()
            if not isinstance(key,str) or not re.fullmatch(r"[A-Za-z0-9_-]{32,128}",key): raise ValueError()
        except (ValueError, UnicodeDecodeError, KeyError, TypeError):
            return web.json_response({"error":"invalid_pairing"}, status=400)
        # No awaits between uniqueness validation and updating the entry.
        if any(e.entry_id != entry.entry_id and e.options.get(ENABLED) and e.options.get(VEHICLE_ID)==vehicle for e in self.hass.config_entries.async_entries(DOMAIN)):
            return web.json_response({"error":"vehicle_id_in_use"}, status=409)
        options = {**entry.options, ENABLED:True, VEHICLE_ID:vehicle, KEY_HASH:hashlib.sha256(key.encode()).hexdigest()}
        options[UPLOAD_KEY]=key
        self.hass.config_entries.async_update_entry(entry,options=options)
        await self.hass.config_entries.async_reload(entry.entry_id)
        return web.json_response({"paired":True},headers={"Cache-Control":"no-store"})


class LocatorUpload(HomeAssistantView):
    # Compatible with already installed Jolion Locator 0.1.0 APK.
    url = "/api/jolion_locator/v1/{vehicle_id}"
    name = "api:gwm_jolion:locator_upload"
    requires_auth = False

    def __init__(self,hass): self.hass = hass

    async def post(self,request,vehicle_id):
        candidates = [getattr(c,"trip_history",None) for c in self.hass.data[DOMAIN].values()]
        matches = [h for h in candidates if isinstance(h,HybridHistory) and h.enabled and h.entry.options.get(VEHICLE_ID)==vehicle_id]
        key = request.headers.get("X-Jolion-Key","")
        if len(matches)!=1 or not 32<=len(key)<=128 or not hmac.compare_digest(hashlib.sha256(key.encode()).hexdigest(),matches[0].entry.options.get(KEY_HASH,"")):
            return web.json_response({"error":"unauthorized"},status=401)
        body = bytearray()
        async for chunk in request.content.iter_chunked(8192):
            body.extend(chunk)
            if len(body)>MAX_BODY:
                return web.json_response({"error":"payload_too_large"},status=413)
        try:
            points = validate(json.loads(body))
            ack = await matches[0].ingest(points)
        except (ValueError,UnicodeDecodeError):
            return web.json_response({"error":"invalid_batch"},status=400)
        except Exception:
            _LOGGER.exception("Unable to store head-unit GPS batch")
            return web.json_response({"error":"storage_unavailable"},status=503)
        return web.json_response({"version":1,"ack":ack})
