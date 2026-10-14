"""GPS fusion without treating cloud polling time as satellite fix time."""
from bisect import bisect_left
import math

LIVE_MAX_AGE_MS = 120000
SAME_FIX_MS = 2000
ESTIMATED_WINDOW_MS = 30000


def quality(point):
    """Known fix time, then measured accuracy; deterministic tie-break."""
    accuracy = point.get("accuracy_m")
    measured = point.get("accuracy_known", False) and isinstance(accuracy, (float, int)) and math.isfinite(accuracy)
    return (0 if point.get("time_known") else 1, 0 if measured else 1,
            accuracy if measured else math.inf, 0 if point.get("source") == "app" else 1)


def choose_live(app, cloud, now_ms):
    candidates = [p for p in (app, cloud) if p and p["timestamp_ms"] <= now_ms + 30000]
    if not candidates:
        return None
    fresh = [p for p in candidates if now_ms-p["timestamp_ms"] <= LIVE_MAX_AGE_MS]
    if not fresh:
        return max(candidates, key=lambda p: p["timestamp_ms"])
    if len(fresh) == 1:
        return fresh[0]
    a, b = fresh
    # A cached cloud response is not proof of a new vehicle position.
    if a.get("time_known") != b.get("time_known"):
        return a if a.get("time_known") else b
    if abs(a["timestamp_ms"]-b["timestamp_ms"]) <= SAME_FIX_MS:
        return min(fresh, key=quality)
    return max(fresh, key=lambda p: p["timestamp_ms"])


def fuse(app, cloud):
    """Replace only competing measurements, preserving uncovered intervals."""
    left = sorted(app, key=lambda p: (p["timestamp_ms"], p["id"]))
    right = sorted(cloud, key=lambda p: (p["timestamp_ms"], p["id"]))
    # Poll timestamps do not make an unchanged cloud fix fresh. Once accurate
    # app fixes establish a departure from that coordinate, ignore repetitions
    # until cloud coordinates change or the app confirms a return. Keep the raw
    # archive and real outages intact.
    fresh = []
    app_index = 0
    previous_position = None
    matched = contradicted = False
    for point in right:
        position = (point['latitude'], point['longitude'])
        if position != previous_position:
            matched = contradicted = False
            repeated_since = point['timestamp_ms']
            previous_position = position
        while app_index < len(left) and left[app_index]['timestamp_ms'] <= point['timestamp_ms']:
            candidate = left[app_index]
            accuracy = candidate.get('accuracy_m')
            if candidate['timestamp_ms'] >= repeated_since and candidate.get('time_known') and accuracy is not None and 0 < accuracy <= 35:
                dy = math.radians(point['latitude'] - candidate['latitude'])
                dx = math.radians(point['longitude'] - candidate['longitude']) * math.cos(math.radians(candidate['latitude']))
                nearby = 6371000 * math.hypot(dx, dy) <= 120
                if nearby:
                    matched = True
                    contradicted = False
                elif matched:
                    contradicted = True
            app_index += 1
        if not point.get('time_known') and contradicted:
            continue
        fresh.append(point)
    right = fresh
    result = []
    for own, other in ((left, right), (right, left)):
        times = [p["timestamp_ms"] for p in other]
        for point in own:
            index = bisect_left(times, point["timestamp_ms"])
            neighbours = other[max(0,index-1):index+1]
            if neighbours:
                nearest = min(neighbours, key=lambda p: abs(p["timestamp_ms"]-point["timestamp_ms"]))
                window = SAME_FIX_MS if point.get("time_known") and nearest.get("time_known") else ESTIMATED_WINDOW_MS
                if abs(nearest["timestamp_ms"]-point["timestamp_ms"]) <= window and quality(nearest) < quality(point):
                    continue
            result.append(point)
    # One unambiguous location per timestamp; do not average different positions.
    unique = {}
    for point in result:
        stamp = point["timestamp_ms"]
        if stamp not in unique or quality(point) < quality(unique[stamp]):
            unique[stamp] = point
    return [unique[t] for t in sorted(unique)]


def cloud_point(stamp, location):
    """The current GWM API supplies neither measured accuracy nor GPS fix time."""
    try:
        if isinstance(location.get("latitude"),bool) or isinstance(location.get("longitude"),bool):
            return None
        lat, lon = float(location["latitude"]), float(location["longitude"])
        if not math.isfinite(lat) or not math.isfinite(lon) or not -90 <= lat <= 90 or not -180 <= lon <= 180 or (lat == 0 and lon == 0):
            return None
        return {"id": f"cloud-{int(stamp*1000)}", "timestamp_ms": int(stamp*1000),
                "latitude": lat, "longitude": lon, "accuracy_m": None,
                "speed_kmh": None, "bearing": None, "altitude_m": None,
                "source": "cloud", "time_known": False, "accuracy_known": False}
    except (ValueError, TypeError, KeyError):
        return None
