"""Local trip observations and bounded calendar queries (no cloud history)."""
from __future__ import annotations

import asyncio
from datetime import date, datetime, time, timedelta
import math
from pathlib import Path
import sqlite3
from zoneinfo import ZoneInfo


GPS_JITTER_KM = 0.03
MIN_MOVING_SPEED_KMH = 3.0
MIN_PARKING_SECONDS = 600
MIN_STATIONARY_SECONDS = 60
MAX_GPS_SPEED_KMH = 250
# A drawn route is decimated to at most this many points. 5000 thinned the app's
# 1 Hz fixes so far that a day turned into long straight "flights" between samples
# tens of seconds apart; 30000 keeps a full day at its native cadence while still
# bounding the payload for a month.
MAX_ROUTE_POINTS = 30000
PARKING_RADIUS_KM = GPS_JITTER_KM
PARKING_BASELINE_SECONDS = 7 * 86400
# The first row of a stationary run is one noisy sample, and a parked receiver
# drifts: on the field archive one car wandered 430 m from the middle of its own
# cloud overnight, so testing 30 m against that first row cut a single parking
# into a dozen markers. Measure the run against its own mean, and give a car that
# has stood for minutes more room before it counts as gone - a car that really
# left resumed 2915 m away.
PARKING_RADIUS_M = 120
DEPARTURE_RADIUS_KM = 0.5
LONG_STOP_SECONDS = 300
# How far apart two fragments of the same parking may sit in time before they are
# treated as separate stops. A phone that sleeps wakes up often, so the cuts it
# causes can be tens of minutes apart while the car never moved.
PARKING_SESSION_SECONDS = 3600
# A position that stays frozen for half an hour and can only be entered and left
# with a jump no car can drive is a cached cloud reading, not travel. The field
# case: 4148 identical fixes 107 km from home, entered 460 s after the car parked
# and left the same way, while the odometer never moved. The run used to become a
# 109 km leg in each direction - one 230 km "trip" for a day the car drove 11 km -
# and it hid the parking that spans it.
FROZEN_RADIUS_M = 30
FROZEN_MIN_SECONDS = 1800


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


def movement_speed(km, seconds):
    """Return average speed and movement status for one connected GPS interval."""
    if seconds <= 0:
        return None, "unknown"
    speed = km / seconds * 3600
    if speed < MIN_MOVING_SPEED_KMH:
        return 0.0, "stationary"
    return speed, "moving"


def gps_jump(km, seconds):
    """Use the same plausibility limit for routes and parking."""
    return seconds > 0 and km > seconds / 3600 * MAX_GPS_SPEED_KMH + 0.1


def stale_run_indices(rows):
    """Indices of a frozen position that no car could have reached or left.

    The T-Box keeps repeating the last coordinate it knew while the car stands
    still, then jumps back to the real one. Both jumps look like 109 km drives at
    a speed nothing on the road drives, and the run between them looks like a
    parking far from home. Dropping the run leaves the real hole in the
    observations, which the route, the parking detector and the trip windows
    already understand.
    """
    total = len(rows)
    drop = set()
    index = 0
    while index < total:
        first = rows[index]
        if first[1] is None or first[2] is None:
            index += 1
            continue
        last = index
        while (last + 1 < total and rows[last + 1][1] is not None
               and rows[last + 1][2] is not None
               and distance(first, rows[last + 1]) * 1000 <= FROZEN_RADIUS_M):
            last += 1
        if last > index and rows[last][0] - first[0] >= FROZEN_MIN_SECONDS:
            before_index = index - 1
            while before_index >= 0 and (rows[before_index][1] is None or rows[before_index][2] is None):
                before_index -= 1
            after_index = last + 1
            while after_index < total and (rows[after_index][1] is None or rows[after_index][2] is None):
                after_index += 1
            before = rows[before_index] if before_index >= 0 else None
            after = rows[after_index] if after_index < total else None
            entered = before is not None and gps_jump(distance(before, first), first[0] - before[0])
            left = after is not None and gps_jump(distance(rows[last], after), after[0] - rows[last][0])
            # A run that can be reached plausibly is a real place; a run that ends
            # in the same direction it was reached from is a real departure.
            # Requiring both jumps keeps a car that was towed or carried overnight
            # (no run at all, only a large plausible gap) and a real parking.
            if entered and (after is None or left):
                drop.update(range(index, last + 1))
        index = last + 1
    return drop


ROUTE_TOLERANCE_M = 4.0


def line_offset_m(anchor, end, point):
    """Distance in metres from point to the straight line anchor->end."""
    scale = math.cos(math.radians(anchor[0])) * 111320.0
    bx, by = (end[1] - anchor[1]) * scale, (end[0] - anchor[0]) * 110540.0
    px, py = (point[1] - anchor[1]) * scale, (point[0] - anchor[0]) * 110540.0
    length = bx * bx + by * by
    if not length:
        return math.hypot(px, py)
    return abs(px * by - py * bx) / math.sqrt(length)


def thin_route(points, kinds, budget, tolerance=ROUTE_TOLERANCE_M):
    """Return the indices worth drawing for one run of fixes.

    Uniform stride sampling kept every N-th fix, so a turn that fell between two
    samples was drawn as a straight diagonal and a short standstill - three
    vertices wide - thinned down to a single point and disappeared. Deviation
    thinning drops only the fixes that repeat what their neighbours already
    describe and keeps every vertex that actually bends the line. Kind changes are
    kept unconditionally for the same reason: a standstill is one vertex wide.
    """
    count = len(points)
    if count <= 2 or budget >= count:
        return list(range(count))
    floors = {0, count - 1}
    for index in range(1, len(kinds)):
        if kinds[index] != kinds[index - 1]:
            floors.update((index, index + 1))
    keep = [0]
    anchor = 0
    for index in range(1, count - 1):
        if index in floors or line_offset_m(points[anchor], points[index + 1], points[index]) > tolerance:
            keep.append(index)
            anchor = index
    keep.append(count - 1)
    if len(keep) > budget:
        # The payload cap wins over fidelity only when even the bent vertices do
        # not fit; the run is then sampled evenly, which still keeps its ends.
        step = math.ceil((len(keep) - 1) / max(1, budget - 1))
        keep = sorted(set(keep[::step]) | {0, count - 1})
    return keep


def parking_spots(rows, minimum_seconds=MIN_PARKING_SECONDS, measured_speeds=None):
    """Keep confirmed stops; never infer parking across missing observations.

    The one exception is a hole the odometer proves the car sat through: the run
    continues across it and the hole is reported as an interruption, so one
    parking stays one marker with its real start and end.
    """
    spots = []
    anchor = previous = None
    anchor_odometer = None
    trusted = True
    interruptions = []
    # Running mean of the stationary run: it does not drift the way a single fix does.
    lat_sum = lon_sum = 0.0
    count = 0

    def mean():
        return (lat_sum/count, lon_sum/count)

    def restart(row):
        nonlocal lat_sum, lon_sum, count
        lat_sum, lon_sum, count = row[1], row[2], 1
        interruptions.clear()

    def finish(ended):
        if trusted and anchor is not None and previous[0] - anchor[0] >= minimum_seconds:
            latitude, longitude = mean()
            spot = {"latitude":latitude, "longitude":longitude,
                    "start":anchor[0], "end":ended,
                    "observed_until":previous[0],
                    "duration":int(previous[0] - anchor[0])}
            if interruptions:
                spot["interruptions"] = list(interruptions)
            spots.append(spot)

    for row in rows:
        if row[1] is None or row[2] is None:
            finish(None)
            anchor = previous = None
            anchor_odometer = None
            continue
        if previous is None:
            anchor = previous = row
            anchor_odometer = row[3]
            restart(row)
            continue
        delta = row[0] - previous[0]
        if delta <= 0:
            continue
        if gps_jump(distance(previous, row), delta):
            # Repeated cached coordinates followed by a jump do not prove a stop.
            # The destination is uncertain too until plausible movement resumes.
            anchor = previous = row
            anchor_odometer = row[3]
            restart(row)
            trusted = False
            continue
        if delta > 600:
            # A hole in the observations is not a departure by itself. When the
            # position reappears where the run already stood and a real odometer
            # reading did not move across the hole, the car stood there all along:
            # continue the run, so one parking keeps its real start and end
            # instead of ending where the receiver went quiet. Without that
            # reading missing time stays missing - a position alone cannot tell a
            # car that was towed from a fix that was cached.
            latitude, longitude = mean()
            returned = distance((anchor[0], latitude, longitude, None), row) <= DEPARTURE_RADIUS_KM
            unchanged = (anchor_odometer is not None and row[3] is not None
                         and row[3] - anchor_odometer <= 0.1)
            if trusted and returned and unchanged and row[0] - anchor[0] >= minimum_seconds:
                interruptions.append([previous[0], row[0]])
                lat_sum += row[1]
                lon_sum += row[2]
                count += 1
                previous = row
                continue
            finish(None)
            anchor = previous = row
            anchor_odometer = row[3]
            restart(row)
            continue
        if anchor_odometer is None and row[3] is not None:
            anchor_odometer = row[3]
        odo_moved = row[3] is not None and anchor_odometer is not None and row[3] > anchor_odometer
        standing = previous[0] - anchor[0] >= LONG_STOP_SECONDS
        latitude, longitude = mean()
        # The wide radius is only safe while the odometer corroborates it: a real
        # reading that has not moved proves the car stood still, so a drifting
        # receiver cannot chop the parking up. With no reading at all the strict
        # jitter radius stays, and a receiver jump is still never called parking.
        # A coarse cloud odometer can lag hundreds of metres behind GNSS.
        # In a Locator history it must not extend parking into the departure.
        limit = DEPARTURE_RADIUS_KM if (standing and anchor_odometer is not None and measured_speeds is None) else PARKING_RADIUS_KM
        displaced = distance((anchor[0], latitude, longitude, None), row) > limit
        measured = (measured_speeds or {}).get(int(row[0]*1000))
        moving = measured is not None and measured >= MIN_MOVING_SPEED_KMH
        if displaced or odo_moved or moving:
            finish(previous[0])
            anchor = row
            anchor_odometer = row[3]
            restart(row)
            if displaced:
                trusted = True
        else:
            lat_sum += row[1]
            lon_sum += row[2]
            count += 1
        previous = row
    finish(None)
    return spots


def period(start, end, zone):
    first, last = date.fromisoformat(start), date.fromisoformat(end)
    if last < first or (last-first).days >= 366:
        raise ValueError("Выберите период от 1 до 366 дней")
    tz = ZoneInfo(zone)
    return (datetime.combine(first, time.min, tz).timestamp(),
            datetime.combine(last + timedelta(days=1), time.min, tz).timestamp())


def join_parking_observations(stops, rows):
    """Group short interruptions at the same place, without counting missing time."""
    indices = {row[0]: index for index, row in enumerate(rows)}
    grouped = []
    for stop in stops:
        previous = grouped[-1] if grouped else None
        if previous and previous["end"] is None and 0 < stop["start"] - previous["observed_until"] <= PARKING_SESSION_SECONDS:
            between = rows[indices[previous["observed_until"]]:indices[stop["start"]]+1]
            odometer = between[0][3]
            same_place = distance((0, previous["latitude"], previous["longitude"]),
                                  (0, stop["latitude"], stop["longitude"])) <= PARKING_RADIUS_KM
            stationary = all((r[1] is None or r[2] is None or
                              distance(between[0], r) <= PARKING_RADIUS_KM) and
                             (r[3] is None or r[3] == odometer) for r in between)
            if same_place and stationary and odometer is not None and between[-1][3] == odometer:
                previous.setdefault("interruptions", []).append([previous["observed_until"], stop["start"]])
                previous["end"] = stop["end"]
                previous["observed_until"] = stop["observed_until"]
                previous["duration"] += stop["duration"]
                continue
        grouped.append(dict(stop))
    return grouped


def summarize(rows, start, end, zone, measured_speeds=None, break_before=None):
    """Count cumulative mileage independently of delayed or missing GPS fixes."""
    tz = ZoneInfo(zone)
    low, high = period(start, end, zone)
    # One cached coordinate is not a day of travel. Drop such a run before it can
    # become a segment, a trip window or a parking far from home.
    stale = stale_run_indices(rows)
    if stale:
        rows = [row for index, row in enumerate(rows) if index not in stale]
    # Read preceding observations to keep a stop's observed start across midnight.
    parking_rows = [row for row in rows if low - PARKING_BASELINE_SECONDS <= row[0] < high]
    stationary_runs = parking_spots(parking_rows, MIN_STATIONARY_SECONDS, measured_speeds)
    # Join before measuring the length. A hole in the observations cuts a parking
    # into pieces, and filtering the pieces first threw away exactly the fragments
    # that would have grown into a real stop, so a car parked for hours ended up
    # with no marker at all.
    stops = join_parking_observations(stationary_runs, parking_rows)
    stops = [stop for stop in stops if stop["duration"] >= MIN_PARKING_SECONDS]
    stops = [stop for stop in stops if stop["observed_until"] >= low]
    stop_index = 0
    days, segments, segment_edges, gaps, segment_timestamps = {}, [], [], [], []
    # A hole with odometer readings on both sides is travel the receiver missed:
    # the card draws it as a grey dashed link instead of leaving two tracks that
    # look unrelated. Coordinates alone never justify the link.
    gap_links = []
    previous = None
    last_fix = None
    odometer = None
    segment = edges = None
    for row in rows:
        stamp, lat, lon, odo = row
        if stamp < low:
            if odo is not None:
                odometer = max(odometer, odo) if odometer is not None else odo
            continue
        if stamp >= high:
            break
        day = datetime.fromtimestamp(stamp, tz).date().isoformat()
        info = days.setdefault(day, {"date":day, "gps_km":0.0, "odo_km":0.0,
                                    "odo_pairs":0, "samples":0, "gaps":0,
                                    "moving_seconds":0.0})
        info["samples"] += 1
        valid = lat is not None and lon is not None
        same_day = previous and datetime.fromtimestamp(previous[0], tz).date().isoformat() == day
        delta = stamp - previous[0] if previous else 0
        comparable = valid and previous and previous[1] is not None and previous[2] is not None
        km = distance(previous, row) if comparable else 0
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
            linked = connected and comparable
            explicit_break=int(stamp*1000) in (break_before or ())
            if explicit_break:linked=False
            if linked and gps_jump(km, delta):
                linked = False
                info["gaps"] += 1
            if linked:
                while stop_index < len(stationary_runs) and stationary_runs[stop_index]["observed_until"] < stamp:
                    stop_index += 1
                parked = (stop_index < len(stationary_runs) and previous[0] >= stationary_runs[stop_index]["start"]
                          and stamp <= stationary_runs[stop_index]["observed_until"])
                speed, kind = (0.0, "stationary") if parked else movement_speed(km, delta)
                measured = (measured_speeds or {}).get(int(stamp*1000))
                if measured is not None:
                    speed, kind = measured, "moving" if measured >= MIN_MOVING_SPEED_KMH else "stationary"
                if kind == "moving":
                    info["gps_km"] += km
                edges.append((speed, kind, km, delta, previous[0]))
                if kind == "moving":
                    info["moving_seconds"] += delta
            else:
                segment = []
                edges = []
                segments.append(segment)
                segment_edges.append(edges)
                segment_timestamps.append([])
                if last_fix and not explicit_break and (lat, lon) != (last_fix[1], last_fix[2]):
                    gaps.append([[last_fix[1], last_fix[2]], [lat, lon]])
                    travelled = distance(last_fix, row)
                    moved = (round(row[3] - last_fix[3], 2)
                             if row[3] is not None and last_fix[3] is not None
                             and row[3] >= last_fix[3] else None)
                    gap_links.append({"from": [last_fix[1], last_fix[2]], "to": [lat, lon],
                                      "seconds": int(stamp - last_fix[0]),
                                      "distance_km": round(travelled, 2),
                                      "odometer_km": moved})
            segment.append([lat, lon])
            segment_timestamps[-1].append(stamp)
            last_fix = row
        else:
            segment = edges = None
        previous = row
    total = 0.0
    methods = set()
    for info in days.values():
        method = "odometer" if info["odo_pairs"] else "gps"
        info["moving_seconds"] = int(info["moving_seconds"])
        info["method"] = method
        info["km"] = round(info["odo_km"] if method == "odometer" else info["gps_km"], 2)
        total += info["km"]
        methods.add(method)
    trip_windows = []
    active = []
    previous_trip = None

    def close_trip():
        if len(active) > 1:
            trip_windows.append({"start":active[0][0], "end":active[-1][0],
                                 "seconds":int(active[-1][0]-active[0][0]),
                                 "km":round(sum(distance(a,b) for a,b in zip(active,active[1:])),2)})

    for row in rows:
        stamp, lat, lon, _ = row
        if stamp < low or stamp >= high or lat is None or lon is None:
            continue
        if previous_trip is not None:
            step = stamp - previous_trip[0]
            # A position no car can reach in the time given is not travel: it
            # neither joins two windows nor adds its own distance to either. The
            # field case was one 230 km "trip" for a day the car drove 11 km.
            if step > 600 or gps_jump(distance(previous_trip, row), step):
                close_trip()
                active.clear()
        active.append(row)
        previous_trip = row
    close_trip()
    # Bound the drawn payload while keeping the shape of the route.
    total_fixes = sum(map(len, segments))
    routes, route_speeds, route_kinds, route_times = [], [], [], []
    for points, edges, timestamps in zip(segments, segment_edges, segment_timestamps):
        if total_fixes > MAX_ROUTE_POINTS:
            budget = max(2, MAX_ROUTE_POINTS * len(points) // total_fixes)
            indices = thin_route(points, [edge[1] for edge in edges], budget)
        else:
            indices = list(range(len(points)))
        # Whole seconds and metres: the client draws and labels the route, so the
        # float noise of the cloud timestamps only made the JSON bigger.
        reduced = [[round(points[index][0], 6), round(points[index][1], 6)] for index in indices]
        reduced_speeds, reduced_kinds = [], []
        for start_index, end_index in zip(indices, indices[1:]):
            grouped = edges[start_index:end_index]
            moving = [edge for edge in grouped if edge[1] == "moving"]
            speed, kind = movement_speed(
                sum(edge[2] for edge in moving),
                sum(edge[3] for edge in moving),
            ) if moving else (0.0, "stationary")
            if moving and measured_speeds:
                duration=sum(edge[3] for edge in moving)
                speed=sum(edge[0]*edge[3] for edge in moving)/duration if duration else None
            reduced_speeds.append(round(speed, 1) if speed is not None else None)
            reduced_kinds.append(kind)
        routes.append(reduced)
        route_speeds.append(reduced_speeds)
        route_kinds.append(reduced_kinds)
        route_times.append([int(timestamps[index]) for index in indices])
    return {"km":round(total, 2), "method":next(iter(methods)) if len(methods)==1 else "mixed",
            "days":list(days.values()), "segments":routes[:5000],
            "segment_speeds_kmh":route_speeds[:5000], "segment_kinds":route_kinds[:5000],
            "segment_timestamps":route_times[:5000], "trips":trip_windows,
            "gaps":gaps[:5000], "gap_links":gap_links[:5000], "parking_spots":stops[:1000],
            "samples":sum(day["samples"] for day in days.values()),
            "moving_seconds":sum(day["moving_seconds"] for day in days.values()),
            "first":rows[0][0] if rows else None, "last":rows[-1][0] if rows else None,
            "simplified":sum(map(len, routes))<total_fixes or len(routes)>MAX_ROUTE_POINTS, "timezone":zone,
            "start":start, "end":end}


def playback(points):
    """Keep every timestamp for the slider; do not invent missing fixes."""
    result=[]
    previous=None
    for point in points:
        p=dict(point)
        p['speed_estimated']=False
        if p.get('speed_kmh') is None and previous and not p.get('display_break') and p.get('source')==previous.get('source'):
            dt=(p['timestamp_ms']-previous['timestamp_ms'])/1000
            if 0 < dt <= 600:
                speed=distance((0,previous['latitude'],previous['longitude'],None),(0,p['latitude'],p['longitude'],None))/dt*3600
                if speed <= 250:
                    p['speed_kmh']=round(speed,1)
                    p['speed_estimated']=True
        result.append({k:p.get(k) for k in ('timestamp_ms','latitude','longitude','speed_kmh','speed_estimated','source','accuracy_m','speed_accuracy_kmh','display_filtered','display_break')})
        previous=p
    return result


def cloud_playback(rows,start,end,zone):
    low,high=period(start,end,zone)
    return playback([dict(timestamp_ms=int(r[0]*1000),latitude=r[1],longitude=r[2],speed_kmh=None,source='cloud') for r in rows if low<=r[0]<high and r[1] is not None and r[2] is not None])


def with_archive(rows, archive, start, end, zone, measured_speeds=None, break_before=None):
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
    # The playback and the last position are built from this route, so the cached
    # run has to leave it here as well: summarize() drops its own copy below.
    stale = stale_run_indices(route)
    if stale:
        route = [row for index, row in enumerate(route) if index not in stale]
    local_odo = [(r[0], None, None, r[3]) for r in rows if r[3] is not None]
    mileage = merge(odo, local_odo, 3)
    # Attach the latest known odometer without using future readings.
    mileage_index = 0
    latest_odo = None
    enriched_route = []
    for row in route:
        while mileage_index < len(mileage) and mileage[mileage_index][0] <= row[0]:
            if mileage[mileage_index][3] is not None:
                latest_odo = mileage[mileage_index][3]
            mileage_index += 1
        enriched_route.append((row[0], row[1], row[2], latest_odo))
    result = summarize(enriched_route, start, end, zone, measured_speeds, break_before)
    result['playback']=cloud_playback(enriched_route,start,end,zone)
    _, high = period(start, end, zone)
    last_position = next((row for row in reversed(enriched_route)
                          if row[0] < high and row[1] is not None and row[2] is not None), None)
    result["last_position"] = ({"latitude":last_position[1], "longitude":last_position[2],
                                "observed_at":last_position[0]} if last_position else None)
    daily = {day["date"]:day for day in result["days"]}
    for day in summarize(sorted(mileage), start, end, zone)["days"]:
        if day["odo_pairs"]:
            previous_day = daily.get(day["date"])
            if previous_day:
                day["moving_seconds"] = previous_day["moving_seconds"]
            daily[day["date"]] = day
    result["days"] = sorted(daily.values(), key=lambda day:day["date"])
    result["km"] = round(sum(day["km"] for day in daily.values()), 2)
    methods = {day["method"] for day in daily.values()}
    result["method"] = next(iter(methods)) if len(methods)==1 else "mixed"
    result["moving_seconds"] = sum(day["moving_seconds"] for day in daily.values())
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
        db = self._connect()
        try:
            db.execute("INSERT OR REPLACE INTO points VALUES (?, ?, ?, ?)", (stamp, lat, lon, odo))
            db.execute("DELETE FROM points WHERE ts < ?", (stamp-self.retention*86400,))
            db.commit()
        finally:
            db.close()

    async def append(self, stamp, location):
        async with self.lock:
            await self.hass.async_add_executor_job(self._append, stamp, location)

    def _query(self, start, end, zone, archive=None, raw=False, include_app=True, include_cloud=True):
        if not include_app and not include_cloud:
            result = summarize([], start, end, zone)
            result["retention_days"] = self.retention
            return result
        low, high = period(start, end, zone)
        db = self._connect()
        try:
            rows = db.execute("SELECT ts,lat,lon,odo FROM points WHERE ts >= ? AND ts < ? ORDER BY ts", (low - PARKING_BASELINE_SECONDS, high)).fetchall()
            odometer_baseline = db.execute("SELECT ts,NULL,NULL,odo FROM points WHERE ts < ? AND odo IS NOT NULL ORDER BY ts DESC LIMIT 1", (low,)).fetchone()
            if odometer_baseline and all(row[0] != odometer_baseline[0] for row in rows):
                rows.append(odometer_baseline)
                rows.sort(key=lambda row: row[0])
        finally:
            db.close()
        # The source switches select GPS geometry. Recorder odometer readings are
        # independent of that choice and remain available in every GPS mode.
        route_rows = rows if include_cloud else [(row[0], None, None, row[3]) for row in rows]
        gps = archive[0] if archive and include_cloud else []
        mileage = [row for row in rows if row[3] is not None]
        if archive:
            mileage.extend(row for row in archive[1] if row[3] is not None)
        result = with_archive(route_rows, (gps, mileage), start, end, zone)
        result["retention_days"] = self.retention
        return result

    async def query(self, start, end, zone, archive=None, raw=False, include_app=True, include_cloud=True):
        async with self.lock:
            return await self.hass.async_add_executor_job(self._query, start, end, zone, archive, raw, include_app, include_cloud)
