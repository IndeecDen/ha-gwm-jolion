"""Durable GPS archive and pure validation/analysis, independent of Home Assistant."""
import math
from contextlib import contextmanager
import re
import sqlite3
import time
from pathlib import Path

MAX_BATCH = 500

# A parked car sleeps: neither the T-Box nor the phone keeps sending fixes. A long
# silence therefore does not by itself mean the car moved.
INFERRED_GAP_MS = 600_000          # only gaps of 10 minutes and longer qualify
INFERRED_PARKING_RADIUS_M = 120    # measured on a real archive: same place 35-100 m,
                                   # a genuinely moved car resumed 2915 m away
ODOMETER_TOLERANCE_KM = 0.1        # below this the car did not roll
ODOMETER_SEARCH_MS = 900_000       # how far from a gap to accept an odometer reading
MERGE_WINDOW_MS = 120_000          # contiguous stops belong to one parking
# A phone that loses signal while parked wakes up many times over a night, so the
# inferred stops it produces can be half an hour apart while the car never moved.
# Merging them over two minutes left the field-test day with fourteen markers on
# one driveway; the merge is safe at this length because it still requires the two
# stops to be within the parking radius of each other.
PARKING_SESSION_MS = 3_600_000
# A stationary run must not be judged against its first fix. Measured on the field
# archive: one car parked overnight wandered 430 m from the centre of its own
# cloud, and every 30 m step chopped the run into another "stop". The radius is the
# same 120 m that already separates "still parked" from "really moved" across a
# gap, and the reported position is the mean of the run instead of its first point.
STATIONARY_RADIUS_M = 120
MIN_STATIONARY_MS = 120_000       # shorter than this is a traffic light, not parking
# A parked phone reports instantaneous speeds of 7-27 km/h while standing still.
# Speed is a derivative of position, and the position is what proves movement, so
# after a few minutes of standing the run stops believing speed on its own. Short
# runs still trust it: that is what keeps a traffic jam from being read as parking.
LONG_STOP_MS = 300_000
# A car that has already stood still has to get much further away before the stop
# is considered over. The same parked phone wandered 430 m from the centre of its
# own cloud over one night, while a car that genuinely left resumed 2915 m away, so
# 500 m separates drift from departure without inventing a second parking.
DEPARTURE_RADIUS_M = 500


def number(value, minimum, maximum):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError("Invalid numeric field")
    return value


def accuracy_meters(value):
    """A GPS accuracy Home Assistant can always use, never None.

    ``TrackerEntity.location_accuracy`` is declared ``-> float`` with a default
    of 0, and Home Assistant hands it straight to zone matching. A None there
    reaches ``zone_dist - zone_radius < radius`` and raises TypeError while the
    state is written, which removes the whole device_tracker entity instead of
    just degrading it. Cloud positions carry no measured accuracy, so the unknown
    case is normal here and has to collapse to 0.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0
    meters = float(value)
    if not math.isfinite(meters) or meters < 0:
        return 0
    return meters


def validate(payload, now_ms=None):
    now_ms = now_ms or int(time.time() * 1000)
    if not isinstance(payload, dict) or type(payload.get("version")) is not int or payload["version"] != 1:
        raise ValueError("Unsupported protocol")
    rows = payload.get("points")
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_BATCH:
        raise ValueError("Invalid batch size")
    result = []
    ids = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Invalid point")
        uid = row.get("id")
        if not isinstance(uid, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{16,80}", uid) or uid in ids:
            raise ValueError("Invalid or repeated id")
        ids.add(uid)
        stamp = row.get("timestamp_ms")
        if type(stamp) is not int:
            raise ValueError("Timestamp must be integer milliseconds")
        point = {
            "id": uid,
            "timestamp_ms": number(stamp, 1577836800000, now_ms + 300000),
            "latitude": number(row.get("latitude"), -90, 90),
            "longitude": number(row.get("longitude"), -180, 180),
            "accuracy_m": number(row.get("accuracy_m"), 0, 100),
        }
        for field, low, high in [("speed_accuracy_kmh", 0, 1000000), ("speed_kmh", 0, 400), ("bearing", 0, 360), ("altitude_m", -1000, 15000)]:
            value = row.get(field)
            point[field] = None if value is None else number(value, low, high)
        result.append(point)
    return result


class Archive:
    def __init__(self, path):
        self.path = str(path)

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA synchronous=FULL")
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def initialize(self):
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("CREATE TABLE IF NOT EXISTS points (id TEXT PRIMARY KEY, timestamp_ms INTEGER NOT NULL, latitude REAL NOT NULL, longitude REAL NOT NULL, accuracy_m REAL NOT NULL, speed_kmh REAL, bearing REAL, altitude_m REAL, received_ms INTEGER NOT NULL)")
            conn.execute("CREATE INDEX IF NOT EXISTS sample_time ON points(timestamp_ms)")
            conn.execute("CREATE INDEX IF NOT EXISTS receive_time ON points(received_ms)")
            conn.execute('CREATE TABLE IF NOT EXISTS relay_receipts (receipt TEXT PRIMARY KEY)')
            if 'speed_accuracy_kmh' not in {r[1] for r in conn.execute('PRAGMA table_info(points)')}:
                conn.execute('ALTER TABLE points ADD COLUMN speed_accuracy_kmh REAL')

    def relay_seen(self,receipt):
        with self.connect() as conn:
            return conn.execute('SELECT 1 FROM relay_receipts WHERE receipt=?',(receipt,)).fetchone() is not None

    def relay_mark(self,receipt):
        with self.connect() as conn:
            conn.execute('INSERT OR IGNORE INTO relay_receipts VALUES (?)',(receipt,))

    def ingest(self, points, now_ms=None):
        now_ms = now_ms or int(time.time() * 1000)
        fields = ("id", "timestamp_ms", "latitude", "longitude", "accuracy_m", "speed_kmh", "bearing", "altitude_m", "speed_accuracy_kmh")
        with self.connect() as conn:
            for p in points:
                existing = conn.execute("SELECT * FROM points WHERE id=?", (p["id"],)).fetchone()
                if existing and any(existing[k] != p.get(k) for k in fields if k != 'speed_accuracy_kmh'):
                    raise ValueError("Point id reused with different data")
                if existing and existing['speed_accuracy_kmh'] is not None and p.get('speed_accuracy_kmh') is not None and existing['speed_accuracy_kmh'] != p['speed_accuracy_kmh']:
                    raise ValueError("Point id reused with different accuracy")
                conn.execute("INSERT OR IGNORE INTO points ("+','.join(fields)+",received_ms) VALUES (?,?,?,?,?,?,?,?,?,?)", (*[p.get(k) for k in fields], now_ms))
                if existing and existing['speed_accuracy_kmh'] is None and p.get('speed_accuracy_kmh') is not None:
                    conn.execute('UPDATE points SET speed_accuracy_kmh=? WHERE id=?',(p['speed_accuracy_kmh'],p['id']))
        # Return only after commit; retries after lost HTTP replies are idempotent.
        return [p["id"] for p in points]

    def latest(self):
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM points ORDER BY timestamp_ms DESC, accuracy_m ASC, id DESC LIMIT 1").fetchone()
            return dict(row) if row else None

    def prune(self, days=30):
        with self.connect() as conn:
            conn.execute("DELETE FROM points WHERE received_ms<?", (int((time.time()-days*86400)*1000),))

    def history(self, start_ms, end_ms):
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM points WHERE timestamp_ms>=? AND timestamp_ms<? ORDER BY timestamp_ms,id LIMIT 100001", (start_ms, end_ms)).fetchall()
        if len(rows) > 100000:
            raise ValueError("Too many points; choose a shorter interval")
        points = [dict(row) for row in rows]
        analysis = analyze(points)
        # Preserve every point on disk; bound browser payloads for a full day.
        step = max(1, math.ceil(len(points) / 5000))
        shown = points[::step]
        if points and shown[-1] is not points[-1]:
            shown.append(points[-1])
        analysis["segments"] = [s[::step] + ([s[-1]] if len(s) > 1 and (len(s)-1) % step else []) for s in analysis["segments"]]
        return {"points": shown, "total_points": len(points), "sample_step": step, **analysis}


def distance(a, b):
    lat1, lat2 = math.radians(a["latitude"]), math.radians(b["latitude"])
    dlat = lat2-lat1
    dlon = math.radians(b["longitude"]-a["longitude"])
    h = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return 6371000 * 2 * math.asin(math.sqrt(min(1, h)))


def _nearest_odometer(odometers, stamp):
    """Closest odometer reading, or None when nothing is close enough to trust."""
    if not odometers:
        return None
    best = min(odometers, key=lambda t: abs(t - stamp))
    return odometers[best] if abs(best - stamp) <= ODOMETER_SEARCH_MS else None


def infer_gap_stop(previous, point, odometers=None):
    """Return a stop spanning a transmission gap, or None.

    The odometer decides: an unchanged reading proves the car did not roll, and it
    is the only signal that survives a car that was moved by tow. Position alone
    is ambiguous, because a parked car under a bad sky view can drift a hundred
    metres between two fixes of the same spot.
    """
    gap = point["timestamp_ms"] - previous["timestamp_ms"]
    if gap < INFERRED_GAP_MS:
        return None
    before = _nearest_odometer(odometers, previous["timestamp_ms"])
    after = _nearest_odometer(odometers, point["timestamp_ms"])
    if before is not None and after is not None:
        if abs(after - before) > ODOMETER_TOLERANCE_KM:
            return None  # the car really moved; the line must stay broken
        inferred_by = "odometer"
    else:
        # A display break can be a source switch as well as a reception gap. Two
        # points from different systems have no comparable accuracy, so position
        # alone must not bridge one; the odometer path above may.
        if point.get("display_break") or previous.get("display_break"):
            return None
        radius = max(
            INFERRED_PARKING_RADIUS_M,
            (previous.get("accuracy_m") or 0) * 2,
            (point.get("accuracy_m") or 0) * 2,
        )
        if distance(previous, point) > radius:
            return None
        inferred_by = "position"
    return {"start_ms": previous["timestamp_ms"], "end_ms": point["timestamp_ms"],
            "latitude": previous["latitude"], "longitude": previous["longitude"],
            "duration_s": gap / 1000, "inferred": True, "inferred_by": inferred_by}


def _merge_stops(stops):
    """Join an inferred gap stop with the observed stops it continues."""
    if not stops:
        return stops
    ordered = sorted(stops, key=lambda s: s["start_ms"])
    merged = [ordered[0]]
    for stop in ordered[1:]:
        last = merged[-1]
        near = distance(last, stop) <= max(
            INFERRED_PARKING_RADIUS_M, (last.get("accuracy_m") or 0) * 2)
        window = MERGE_WINDOW_MS
        if near and (stop.get("inferred") or last.get("inferred")):
            # Both ends come from the receiver going quiet, so a long silence at
            # the same place is still one parking.
            window = PARKING_SESSION_MS
        contiguous = stop["start_ms"] - last["end_ms"] <= window
        if contiguous and near and (stop.get("inferred") or last.get("inferred")):
            last["end_ms"] = max(last["end_ms"], stop["end_ms"])
            last["duration_s"] = (last["end_ms"] - last["start_ms"]) / 1000
            # Keep the reason the silence was treated as parking, otherwise a
            # merged stop loses the flag the card needs to label it.
            last["inferred"] = bool(last.get("inferred") or stop.get("inferred"))
            last["inferred_by"] = last.get("inferred_by") or stop.get("inferred_by")
            continue
        merged.append(stop)
    return merged


def _accuracy(point):
    """Accuracy usable for a numeric decision.

    A cloud fix has no measured accuracy at all, and comparing None with a number
    would abort the whole history query. Unknown accuracy must simply never
    confirm anything.
    """
    value = point.get("accuracy_m")
    return value if isinstance(value, (int, float)) else float("inf")


def analyze(points, odometers=None):
    """Observed stops, plus parking inferred across a transmission gap.

    Stops are only extended across a gap when the odometer proves the car stood
    still; nothing is ever joined across a gap by position alone when the
    odometer shows movement.
    """
    stops, segments = [], []
    segment, stationary = [], []
    kilometers = 0.0
    prev = None
    # Running mean of the stationary run: the first fix is a single noisy sample,
    # and it drifts, so anchoring to it would end the parking after a few minutes.
    lat_sum = lon_sum = 0.0

    def finish_stop():
        nonlocal lat_sum, lon_sum
        if stationary and stationary[-1]["timestamp_ms"]-stationary[0]["timestamp_ms"] >= MIN_STATIONARY_MS:
            count = len(stationary)
            stops.append({"start_ms": stationary[0]["timestamp_ms"], "end_ms": stationary[-1]["timestamp_ms"],
                          "latitude": lat_sum/count, "longitude": lon_sum/count,
                          "duration_s": (stationary[-1]["timestamp_ms"]-stationary[0]["timestamp_ms"])/1000})
        stationary.clear()
        lat_sum = lon_sum = 0.0

    for p in points:
        delta = p["timestamp_ms"]-prev["timestamp_ms"] if prev else None
        meters = distance(prev, p) if prev else 0
        gap = prev is not None and (p.get('display_break') or delta <= 0 or delta > 120000 or meters/(delta/1000) > 100)
        if gap:
            if segment:
                segments.append(segment)
            segment = []
            # A long silence with the odometer unchanged means the car slept where
            # it stood; treat the silence as the same parking instead of a void.
            if prev is not None and delta >= INFERRED_GAP_MS:
                finish_stop()
                inferred = infer_gap_stop(prev, p, odometers)
                if inferred:
                    inferred["accuracy_m"] = prev.get("accuracy_m")
                    stops.append(inferred)
            # A shorter hole in the uploads does not end a parking either. The car
            # parked on the field test lost its phone stream for 124 s at a time,
            # and every hole cut one stop into pieces - the car had not moved a
            # metre. The run stays open and the next point settles whether the
            # car really left: too far away and the displacement check ends it.
        segment.append([p["latitude"], p["longitude"]])
        if prev and not gap and _accuracy(p) <= 50 and _accuracy(prev) <= 50:
            if (p["speed_kmh"] or 0) > 3 and (prev["speed_kmh"] or 0) > 3:
                kilometers += meters / 1000
        resting = p["speed_kmh"] is not None and p["speed_kmh"] <= 3 and _accuracy(p) <= 50
        centre = None
        if stationary:
            centre = {"latitude": lat_sum/len(stationary), "longitude": lon_sum/len(stationary)}
        standing = bool(stationary) and stationary[-1]["timestamp_ms"]-stationary[0]["timestamp_ms"] >= LONG_STOP_MS
        near = centre is not None and distance(
            centre, p) <= (DEPARTURE_RADIUS_M if standing else STATIONARY_RADIUS_M)

        if centre is not None and not near:
            # Leaving the spot is the only thing that ends a standing parking.
            finish_stop()
        elif standing and near:
            # The car has stood for minutes and has not gone anywhere. Its
            # reported speed jumps to 7-27 km/h and its accuracy climbs past 50 m
            # while it does; neither of those proves movement, and treating them
            # as movement is what shredded one parked night into a dozen markers.
            stationary.append(p)
            lat_sum += p["latitude"]
            lon_sum += p["longitude"]
        elif resting and not p.get("display_break"):
            stationary.append(p)
            lat_sum += p["latitude"]
            lon_sum += p["longitude"]
        else:
            finish_stop()
        prev = p
    finish_stop()
    if segment:
        segments.append(segment)
    return {"segments": segments, "stops": _merge_stops(stops), "distance_km": round(kilometers, 2),
            "max_speed_kmh": max((p["speed_kmh"] or 0 for p in points), default=0)}
