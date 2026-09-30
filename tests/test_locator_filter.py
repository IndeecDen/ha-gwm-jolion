import importlib.util
from pathlib import Path
import math
import random

spec=importlib.util.spec_from_file_location('display_filter',Path(__file__).resolve().parents[1]/'custom_components/gwm_jolion/locator_filter.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
filter_display=module.filter_display

def point(i,x=0,y=0,speed=0,accuracy=15,source='app'):
    return dict(timestamp_ms=1700000000000+i*1000,latitude=55+y/111195,longitude=37+x/63779,accuracy_m=accuracy,speed_kmh=speed,source=source)

def test_stationary_indoor_spider_and_single_speed_spikes():
    random.seed(19)
    raw=[point(i,random.uniform(-150,150),random.uniform(-150,150),speed=25 if i%43==0 else 0) for i in range(600)]
    saved=[dict(p) for p in raw]
    result=filter_display(raw)
    assert len({(p['latitude'],p['longitude']) for p in result})==1
    assert all(p['speed_kmh']==0 for p in result)
    assert raw==saved

def test_slow_parking_manoeuvre_is_retained_after_confirmation():
    raw=[point(i,x=i*.6,speed=2.16,accuracy=3) for i in range(30)]
    assert filter_display(raw)==raw

def test_missing_speed_can_confirm_directed_movement():
    raw=[point(i,x=i,speed=None,accuracy=4) for i in range(30)]
    assert filter_display(raw)==raw

def test_stop_then_depart_retains_departure_points():
    raw=[point(i,x=(i%3)*3) for i in range(20)]+[point(i,x=(i-20)*2,speed=7.2,accuracy=4) for i in range(20,45)]
    filtered=filter_display(raw)
    assert len({p['longitude'] for p in filtered[:20]})==1
    assert filtered[20:]==raw[20:]

def test_moving_outlier_does_not_create_a_spike():
    raw=[point(i,x=i*10,speed=36,accuracy=4) for i in range(20)]
    raw[10]=point(10,x=900,y=1000,speed=36,accuracy=4)
    filtered=filter_display(raw)
    assert filtered[10]['longitude']==filtered[9]['longitude']
    assert filtered[-1]==raw[-1]

def test_cloud_source_switch_and_reception_gap_are_broken():
    raw=[point(0,source='cloud'),point(1,x=900,source='app'),point(90,x=1000,source='app')]
    filtered=filter_display(raw)
    assert filtered[0]==raw[0]
    assert filtered[1]['display_break'] and filtered[2]['display_break']

def test_consistent_reacquired_fixes_resume_without_connecting_jump():
    raw=[point(i,x=i*10+(1000 if i>=10 else 0),speed=36,accuracy=4) for i in range(30)]
    filtered=filter_display(raw)
    assert filtered[-1]==raw[-1]
    assert filtered[10]['display_break']
    assert filtered[10]['longitude']==raw[10]['longitude']

def test_repeated_inconsistent_outliers_do_not_reacquire():
    raw=[point(i,x=i*10,speed=36,accuracy=4) for i in range(10)]
    raw += [point(i,x=1000 if i%2 else -1000,speed=36,accuracy=4) for i in range(10,30)]
    filtered=filter_display(raw)
    assert all(p['longitude']==filtered[9]['longitude'] for p in filtered[10:])

def test_uncertain_speed_does_not_unlock_stationary_drift():
    raw=[dict(point(i,x=(i%30)*.6,speed=8,accuracy=20),speed_accuracy_kmh=10) for i in range(180)]
    saved=[dict(p) for p in raw]
    result=filter_display(raw)
    assert len({p['longitude'] for p in result})==1
    assert all(p['speed_kmh']==0 for p in result)
    assert raw==saved

def test_precise_slow_speed_preserves_parking_manoeuvre():
    raw=[dict(point(i,x=i*.6,speed=2.16,accuracy=3),speed_accuracy_kmh=.2) for i in range(60)]
    assert filter_display(raw)==raw

def test_uncertain_zero_speed_can_use_sustained_coordinates():
    raw=[dict(point(i,x=i*.8,speed=0,accuracy=3),speed_accuracy_kmh=5) for i in range(60)]
    assert filter_display(raw)==raw

def test_uncertain_speed_after_driving_can_confirm_stationary_cluster():
    raw=[dict(point(i,x=i*10,speed=36,accuracy=4),speed_accuracy_kmh=.5) for i in range(20)]
    raw += [dict(point(i,x=200+(i%3),speed=8,accuracy=10),speed_accuracy_kmh=12) for i in range(20,80)]
    result=filter_display(raw)
    assert len({p['longitude'] for p in result[20:]})==1
    assert all(p['speed_kmh']==0 for p in result[20:])

def test_uncertain_moving_speed_does_not_create_false_stop():
    raw=[dict(point(i,x=i*.8,speed=2.88,accuracy=3),speed_accuracy_kmh=5) for i in range(90)]
    assert filter_display(raw)==raw


def test_a_glitch_when_leaving_a_stop_is_not_drawn_as_a_line():
    """The real archive contained a 174 m one-tick jump right after a long stop."""
    raw=[point(i,x=0,speed=0,accuracy=6) for i in range(200)]
    raw+=[point(200,x=174,speed=18.5,accuracy=7)]
    raw+=[point(201+i,x=174+6*(i+1),speed=20+i*.4,accuracy=7) for i in range(20)]
    filtered=filter_display(raw)
    # No drawn step may imply a speed the car cannot reach.
    drawn=0
    for a,b in zip(filtered,filtered[1:]):
        if b.get('display_break') or a.get('display_break'):continue
        if b.get('display_filtered') or a.get('display_filtered'):continue
        dt=(b['timestamp_ms']-a['timestamp_ms'])/1000
        drawn=max(drawn,meters_deg(a,b)/dt*3.6)
    assert drawn<130, drawn
    # The drive itself is still recorded, and the jump is declared, not hidden.
    assert filtered[-1]['longitude']==raw[-1]['longitude']
    assert any(p.get('display_break') for p in filtered)


def test_the_declared_jump_cannot_be_removed_by_a_later_refresh():
    """Without the break the 174 m step is drawn as a line; this pins that down."""
    raw=[point(i,x=0,speed=0,accuracy=6) for i in range(200)]
    raw+=[point(200,x=174,speed=18.5,accuracy=7)]
    raw+=[point(201+i,x=174+6*(i+1),speed=20+i*.4,accuracy=7) for i in range(20)]
    filtered=filter_display(raw)
    jumps=[k for k,p in enumerate(filtered) if p.get('display_break')]
    assert jumps, "разрыв не объявлен"
    # Every break must sit on the impossible step, not somewhere harmless.
    for k in jumps:
        a,b=filtered[k-1],filtered[k]
        dt=(b['timestamp_ms']-a['timestamp_ms'])/1000
        assert meters_deg(a,b)/dt*3.6>130 or filtered[k-1].get('display_filtered')


def test_a_clean_departure_is_not_marked_as_a_break():
    raw=[point(i,x=0,speed=0,accuracy=4) for i in range(200)]
    raw+=[point(200+i,x=2*(i+1),speed=7.2,accuracy=4) for i in range(40)]
    filtered=filter_display(raw)
    assert not any(p.get('display_break') for p in filtered)
    assert filtered[-1]==raw[-1]


def test_a_jump_after_a_drive_still_resumes_as_a_known_re_emergence():
    """A tunnel ends a kilometre away; that re-emergence must be kept."""
    raw=[point(i,x=i*10,speed=36,accuracy=4) for i in range(30)]
    raw+=[point(30+i,x=1000+i*10,speed=36,accuracy=4) for i in range(30)]
    filtered=filter_display(raw)
    assert filtered[-1]==raw[-1]
    assert filtered[30].get('display_break')


def test_a_hold_released_after_a_glitch_keeps_the_anchor_until_it_settles():
    raw=[point(i,x=0,speed=0,accuracy=6) for i in range(200)]
    raw+=[point(200+i,x=300+i*6,speed=20+i*.3,accuracy=7) for i in range(30)]
    filtered=filter_display(raw)
    # Everything while the hold lasted is still the anchor.
    assert all(p['longitude']==raw[0]['longitude'] for p in filtered[:200])
    assert filtered[-1]['longitude']==raw[-1]['longitude']


def test_traffic_light_wobble_with_unreliable_speed_is_not_drawn():
    """Drive up to a light, then stop: speed reads 0-2 km/h with a 10 km/h error."""
    random.seed(7)
    raw=[]
    x=0.0
    for i in range(120):                      # approach, speed is reliable
        x+=9.0
        raw.append(dict(point(i,x=x,speed=32,accuracy=4)))
    for i in range(120,420):                  # at the light, speed is not measurable
        x+=random.uniform(-1.4,1.4)
        raw.append(dict(point(i,x=x,speed=random.uniform(0,2),accuracy=6),speed_accuracy_kmh=10))
    filtered=filter_display(raw)
    # Look only at what the card actually draws after the car stopped.
    drawn=[p for p in filtered[120:] if not p.get('display_held') and not p.get('display_filtered')]
    steps=[]
    for a,b in zip(drawn,drawn[1:]):
        if (b['timestamp_ms']-a['timestamp_ms'])/1000>5:continue
        steps.append((b['longitude']-a['longitude'],b['latitude']-a['latitude'],
                      math.hypot(b['longitude']-a['longitude'],b['latitude']-a['latitude'])))
    turns=0
    for prev,cur in zip(steps,steps[1:]):
        if prev[2]<=0.2 or cur[2]<=0.2:continue
        if prev[0]*cur[0]+prev[1]*cur[1]<0:turns+=1
    assert steps, "после остановки нечего рисовать"
    assert turns<=max(1,len(steps)//20), f"трек зигзагит: {turns} разворотов из {len(steps)} шагов"
    assert sum(1 for p in filtered[120:] if p.get('display_held'))>len(filtered[120:])//2


def test_a_real_creep_still_moves_the_track_under_unreliable_speed():
    raw=[dict(point(i,x=i*.8,speed=0,accuracy=3),speed_accuracy_kmh=5) for i in range(60)]
    assert filter_display(raw)==raw


def meters_deg(a,b):
    import math
    lat1,lat2=math.radians(a['latitude']),math.radians(b['latitude'])
    dlat=lat2-lat1;dlon=math.radians(b['longitude']-a['longitude'])
    h=math.sin(dlat/2)**2+math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return 6371000*2*math.asin(math.sqrt(min(1,h)))
