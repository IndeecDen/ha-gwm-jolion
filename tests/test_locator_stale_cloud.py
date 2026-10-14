"""A cached departure coordinate must not erase a stop recorded after arrival."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'custom_components' / 'gwm_jolion'


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


merge = load('locator_merge')
trips = load('trips')


def app(t, lat):
    return dict(id=f'app-{t}', timestamp_ms=t*1000, latitude=lat, longitude=37,
                accuracy_m=3, accuracy_known=True, time_known=True, source='app')


def cloud(t, lat):
    return merge.cloud_point(t, dict(latitude=lat, longitude=37))


def test_stale_departure_repeats_do_not_poison_arrival_parking():
    phone = [app(100+i*10, 55+i*.001) for i in range(31)]
    cached = [cloud(t, 55) for t in range(0, 1500, 5)]
    arrived = [cloud(t, 55.03) for t in range(1500, 4000, 5)]
    original = [dict(p) for p in cached]
    fused = merge.fuse(phone, cached+arrived)
    assert not [p for p in fused if p['source']=='cloud' and p['timestamp_ms']>400000 and p['latitude']==55]
    assert fused[-1] == arrived[-1]
    rows = [(p['timestamp_ms']/1000,p['latitude'],p['longitude'],None) for p in fused]
    stops = trips.parking_spots(rows)
    assert len(stops)==1 and stops[0]['start']==1500
    assert cached == original
    assert fused == merge.fuse(list(reversed(phone)), list(reversed(cached+arrived)))


def test_cloud_only_and_updated_positions_remain_available():
    cached = [cloud(t, 55) for t in range(0, 200, 5)]
    assert merge.fuse([], cached)==cached
    changed = cloud(200, 55.02)
    assert changed in merge.fuse([app(100,55.01)],cached+[changed])
    assert cached[-1] in merge.fuse([app(100,55)],cached)
    assert cached[-1] in merge.fuse([dict(app(100,55.01),accuracy_m=100)],cached)


def test_new_cloud_repeat_is_not_rejected_using_an_older_phone_fix():
    cached = [cloud(t, 55.02) for t in range(200, 400, 5)]
    assert merge.fuse([app(100,55.01)],cached)==[app(100,55.01),*cached]


def test_unknown_origin_and_confirmed_return_keep_cloud_observations():
    cached = [cloud(t, 55) for t in range(0, 1000, 5)]
    assert cached[-1] in merge.fuse([app(100,55.03)],cached)
    phone = [app(100,55),app(200,55.03),app(500,55)]
    fused = merge.fuse(phone,cached)
    assert not [p for p in fused if p['source']=='cloud' and 250000<p['timestamp_ms']<450000]
    assert cached[-1] in fused
