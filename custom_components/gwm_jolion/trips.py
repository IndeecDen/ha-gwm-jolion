"""Local trip observations and bounded calendar queries (no cloud history)."""
from __future__ import annotations

import asyncio
from datetime import date, datetime, time, timedelta
import math
from pathlib import Path
import sqlite3
from zoneinfo import ZoneInfo


def number(value):
    try:
        result = float(value)
        return result if not isinstance(value, bool) and math.isfinite(result) else None
    except (ValueError, TypeError):
        return None


def distance(a, b):
    lat1, lat2 = math.radians(a[1]), math.radians(b[1])
    dlat, dlon = lat2 - lat1, math.radians(b[2] - a[2])
    h = math.sin(dlat / 2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon / 2)**2
    return 12742 * math.asin(min(1, math.sqrt(h)))


def period(start, end, zone):
    first, last = date.fromisoformat(start), date.fromisoformat(end)
    if last < first or (last-first).days >= 366:
        raise ValueError("Выберите период от 1 до 366 дней")
    tz = ZoneInfo(zone)
    return (datetime.combine(first, time.min, tz).timestamp(),
            datetime.combine(last + timedelta(days=1), time.min, tz).timestamp())


def summarize(rows, start, end, zone):
    """Count cumulative mileage independently of delayed or missing GPS fixes."""
    tz = ZoneInfo(zone)
    low, high = period(start, end, zone)
    days, segments, gaps = {}, [], []
    previous = None
    last_fix = None
    odometer = None
    segment = None
    for row in rows:
        stamp, lat, lon, odo = row
        if stamp < low:
            if odo is not None:
                odometer = max(odometer, odo) if odometer is not None else odo
            continue
        if stamp >= high:
            continue
        day = datetime.fromtimestamp(stamp, tz).date().isoformat()
        info = days.setdefault(day, {"date":day, "gps_km":0.0, "odo_km":0.0,
                                    "odo_pairs":0, "samples":0, "gaps":0})
        info["samples"] += 1
        valid = lat is not None and lon is not None
        same_day = previous and datetime.fromtimestamp(previous[0], tz).date().isoformat() == day
        delta = stamp - previous[0] if previous else 0
        connected = same_day and 0 < delta <= 600
        if same_day and delta > 600:
            info["gaps"] += 1
        # Cloud responses may repeat an old reading for hours, then catch up.
        # Poll interval is not travel time. Never reject mileage using GPS speed.
        if odo is not None:
            if odometer is not None and odo >= odometer:
                diff = odo - odometer
                info["odo_km"] += diff
                info["odo_pairs"] += 1
            if odometer is None or odo > odometer:
                odometer = odo
        if valid:
            linked = connected and previous[1] is not None and previous[2] is not None
            km = distance(previous, row) if linked else 0
            if linked and km > delta / 3600 * 250 + 0.1:
                linked = False
                info["gaps"] += 1
            if linked:
                # Ignore short GPS jitter, without moving the stored coordinates.
                if km >= 0.03:
                    info["gps_km"] += km
            else:
                segment = []
                segments.append(segment)
                if last_fix and (lat, lon) != (last_fix[1], last_fix[2]):
                    gaps.append([[last_fix[1], last_fix[2]], [lat, lon]])
            segment.append([lat, lon])
            last_fix = row
        else:
            segment = None
        previous = row
    total = 0.0
    methods = set()
    for info in days.values():
        method = "odometer" if info["odo_pairs"] else "gps"
        info["method"] = method
        info["km"] = round(info["odo_km"] if method == "odometer" else info["gps_km"], 2)
        total += info["km"]
        methods.add(method)
    # Limit route payload while preserving segment boundaries and endpoints.
    stride = max(1, math.ceil(sum(map(len, segments)) / 5000))
    routes = []
    for points in segments:
        reduced = points[::stride]
        if reduced[-1] != points[-1]: reduced.append(points[-1])
        routes.append(reduced)
    return {"km":round(total, 2), "method":next(iter(methods)) if len(methods)==1 else "mixed",
            "days":list(days.values()), "segments":routes[:5000], "gaps":gaps[:5000], "samples":sum(day["samples"] for day in days.values()),
            "first":rows[0][0] if rows else None, "last":rows[-1][0] if rows else None,
            "simplified":stride > 1 or len(routes)>5000, "timezone":zone,
            "start":start, "end":end}


def with_archive(rows, archive, start, end, zone):
    """Merge both sources throughout the period, including local recording gaps."""
    gps, odo = archive
    def merge(archived, local, value_index):
        merged = {}
        for row in [*archived, *local]:
            key = int(row[0])
            if key not in merged or row[value_index] is not None:
                merged[key] = row
        return sorted(merged.values())
    route = merge(gps, [(r[0], r[1], r[2], None) for r in rows], 1)
    local_odo = [(r[0], None, None, r[3]) for r in rows if r[3] is not None]
    mileage = merge(odo, local_odo, 3)
    result = summarize(sorted(route), start, end, zone)
    daily = {day["date"]:day for day in result["days"]}
    for day in summarize(sorted(mileage), start, end, zone)["days"]:
        if day["odo_pairs"]:
            daily[day["date"]] = day
    result["days"] = sorted(daily.values(), key=lambda day:day["date"])
    result["km"] = round(sum(day["km"] for day in daily.values()), 2)
    methods = {day["method"] for day in daily.values()}
    result["method"] = next(iter(methods)) if len(methods)==1 else "mixed"
    low, high = period(start, end, zone)
    times = [r[0] for r in [*route, *mileage] if low <= r[0] < high]
    result["samples"] = len(set(times))
    result["first"] = min(times) if times else None
    result["last"] = max(times) if times else None
    return result


class TripHistory:
    def __init__(self, hass, entry_id, retention=90):
        self.hass = hass
        self.path = Path(hass.config.path(".storage", f"gwm_jolion_{entry_id}_trips.sqlite"))
        self.retention = max(30, min(365, int(retention)))
        self.lock = asyncio.Lock()

    def _connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=10)
        db.execute("CREATE TABLE IF NOT EXISTS points (ts REAL PRIMARY KEY, lat REAL, lon REAL, odo REAL)")
        return db

    def _append(self, stamp, location):
        lat, lon, odo = (number(location.get(key)) for key in ("latitude", "longitude", "odometer"))
        if lat is None or lon is None or not -90 <= lat <= 90 or not -180 <= lon <= 180 or (lat == 0 and lon == 0):
            lat = lon = None
        if odo is not None and odo < 0: odo = None
        with self._connect() as db:
            db.execute("INSERT OR REPLACE INTO points VALUES (?, ?, ?, ?)", (stamp, lat, lon, odo))
            db.execute("DELETE FROM points WHERE ts < ?", (stamp-self.retention*86400,))
        db.close()

    async def append(self, stamp, location):
        async with self.lock:
            await self.hass.async_add_executor_job(self._append, stamp, location)

    def _query(self, start, end, zone, archive=None):
        low, high = period(start, end, zone)
        with self._connect() as db:
            rows = db.execute("SELECT ts,lat,lon,odo FROM points WHERE ts >= ? AND ts < ? ORDER BY ts", (low, high)).fetchall()
            baseline = db.execute("SELECT ts,NULL,NULL,odo FROM points WHERE ts < ? AND odo IS NOT NULL ORDER BY ts DESC LIMIT 1", (low,)).fetchone()
            if baseline:
                rows.insert(0, baseline)
        db.close()
        result = with_archive(rows, archive or ([], []), start, end, zone)
        result["retention_days"] = self.retention
        return result

    async def query(self, start, end, zone, archive=None):
        async with self.lock:
            return await self.hass.async_add_executor_job(self._query, start, end, zone, archive)
