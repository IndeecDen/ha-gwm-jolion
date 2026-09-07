from pathlib import Path


REMOTE_CARD = Path("custom_components/gwm_jolion/frontend/gwm-jolion-remote-card.js")


def _source() -> str:
    return REMOTE_CARD.read_text(encoding="utf-8")


def test_remote_card_version_and_horizontal_orientation() -> None:
    source = _source()
    assert 'CARD_VERSION = "0.1.0-alpha.19.4"' in source
    assert 'viewBox="0 0 1200 520"' in source
    assert "Капот слева, багажник справа" in source
    assert "левая сторона автомобиля сверху" in source


def test_all_four_doors_use_left_edge_as_hinge() -> None:
    source = _source()
    assert "transform-origin:0% 50%" in source
    assert 'class="door door-fl left-side' in source
    assert 'class="door door-rl left-side' in source
    assert 'class="door door-fr right-side' in source
    assert 'class="door door-rr right-side' in source
    assert ".door.left-side.open" in source
    assert "transform:rotate(-34deg)" in source
    assert ".door.right-side.open" in source
    assert "transform:rotate(34deg)" in source


def test_door_entity_mapping_is_not_swapped() -> None:
    source = _source()
    assert 'doorFl: "_door_front_left_open"' in source
    assert 'doorFr: "_door_front_right_open"' in source
    assert 'doorRl: "_door_rear_left_open"' in source
    assert 'doorRr: "_door_rear_right_open"' in source
    assert '${this._doorLabel("fl", doors.fl)}' in source
    assert '${this._doorLabel("fr", doors.fr)}' in source
    assert '${this._doorLabel("rl", doors.rl)}' in source
    assert '${this._doorLabel("rr", doors.rr)}' in source


def test_headlights_remain_decoupled_from_engine_state() -> None:
    source = _source()
    assert 'class="headlights"' in source
    assert ".headlights.lights-on" in source
    assert "engine-on .headlights" not in source
