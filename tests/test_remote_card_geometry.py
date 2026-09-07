from pathlib import Path


REMOTE_CARD = Path("custom_components/gwm_jolion/frontend/gwm-jolion-remote-card.js")


def _source() -> str:
    return REMOTE_CARD.read_text(encoding="utf-8")


def test_remote_card_version_and_horizontal_orientation() -> None:
    source = _source()
    assert 'CARD_VERSION = "0.1.0-alpha.19.5"' in source
    assert 'viewBox="0 0 1000 390"' in source
    assert "капот слева, багажник справа" in source.lower()
    assert "правая сторона автомобиля сверху, левая снизу" in source


def test_right_side_is_top_and_left_side_is_bottom() -> None:
    source = _source()
    assert 'class="door door-fr top-side' in source
    assert 'class="door door-rr top-side' in source
    assert 'class="door door-fl bottom-side' in source
    assert 'class="door door-rl bottom-side' in source
    assert 'this._doorCallout("fr",doors.fr)' in source
    assert 'this._doorCallout("rr",doors.rr)' in source
    assert 'this._doorCallout("fl",doors.fl)' in source
    assert 'this._doorCallout("rl",doors.rl)' in source


def test_all_four_doors_use_left_edge_as_hinge() -> None:
    source = _source()
    assert "transform-origin:0% 50%" in source
    assert ".door.top-side.open{transform:rotate(-31deg)" in source
    assert ".door.bottom-side.open{transform:rotate(31deg)" in source
    assert 'class="hinge hinge-fr"' in source
    assert 'class="hinge hinge-rr"' in source
    assert 'class="hinge hinge-fl"' in source
    assert 'class="hinge hinge-rl"' in source


def test_door_entity_mapping_is_not_swapped() -> None:
    source = _source()
    assert 'doorFl:"_door_front_left_open"' in source
    assert 'doorFr:"_door_front_right_open"' in source
    assert 'doorRl:"_door_rear_left_open"' in source
    assert 'doorRr:"_door_rear_right_open"' in source


def test_confirmed_driver_window_stays_on_front_left_door() -> None:
    source = _source()
    assert 'window1Raw:"_window_2210001_raw"' in source
    assert 'class="door door-fl bottom-side' in source
    assert 'class="door-window driver-window"' in source
    assert "if(value===1)return 0" in source
    assert "if(value===3)return .52" in source
    assert "if(value===2)return 1" in source


def test_headlights_remain_decoupled_from_engine_state() -> None:
    source = _source()
    assert 'class="headlights"' in source
    assert ".headlight-beam{fill:transparent;opacity:0}" in source
    assert "engine-on .headlights" not in source
