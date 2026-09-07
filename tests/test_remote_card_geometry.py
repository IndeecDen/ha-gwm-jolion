from pathlib import Path


REMOTE_CARD = Path("custom_components/gwm_jolion/frontend/gwm-jolion-remote-card.js")


def _source() -> str:
    return REMOTE_CARD.read_text(encoding="utf-8")


def test_remote_card_version_and_horizontal_orientation() -> None:
    source = _source()
    assert 'CARD_VERSION = "0.1.0-alpha.19.7"' in source
    assert 'viewBox="0 0 1100 520"' in source
    assert "капот слева, багажник справа" in source.lower()
    assert "правая сторона автомобиля сверху, левая снизу" in source
    assert "wide SUV proportions" in source


def test_right_side_is_top_and_left_side_is_bottom() -> None:
    source = _source()
    assert 'class="door door-fr top-side' in source
    assert 'class="door door-rr top-side' in source
    assert 'class="door door-fl bottom-side' in source
    assert 'class="door door-rl bottom-side' in source
    assert 'this._doorCallout("fr", doors.fr)' in source
    assert 'this._doorCallout("rr", doors.rr)' in source
    assert 'this._doorCallout("fl", doors.fl)' in source
    assert 'this._doorCallout("rl", doors.rl)' in source


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
    assert 'doorFl: "_door_front_left_open"' in source
    assert 'doorFr: "_door_front_right_open"' in source
    assert 'doorRl: "_door_rear_left_open"' in source
    assert 'doorRr: "_door_rear_right_open"' in source


def test_field_confirmed_windows_map_to_all_four_physical_panes() -> None:
    source = _source()
    assert 'window1Raw: "_window_2210001_raw"' in source
    assert 'window2Raw: "_window_2210002_raw"' in source
    assert 'window3Raw: "_window_2210003_raw"' in source
    assert 'window4Raw: "_window_2210004_raw"' in source
    assert 'const windowFl = this._windowVisual("window1", "window1Raw")' in source
    assert 'const windowFr = this._windowVisual("window2", "window2Raw")' in source
    assert 'const windowRl = this._windowVisual("window3", "window3Raw")' in source
    assert 'const windowRr = this._windowVisual("window4", "window4Raw")' in source
    assert 'class="door door-fl bottom-side' in source
    assert 'class="door-window driver-window ${windowFl.open ? "window-open" : ""}"' in source
    assert '${windowFr.opacity.toFixed(2)}' in source
    assert '${windowRl.opacity.toFixed(2)}' in source
    assert '${windowRr.opacity.toFixed(2)}' in source
    assert "if (value === 1) return 0" in source
    assert "if (value === 3) return 0.52" in source
    assert "if (value === 2) return 1" in source


def test_status_tiles_always_have_visible_values() -> None:
    source = _source()
    assert 'grid-template-columns:repeat(4,minmax(0,1fr))' in source
    assert 'fuel: ["mdi:fuel", "Топливо", this._value("fuel", "Нет данных"), "info"]' in source
    assert 'mileage: ["mdi:counter", "Пробег", this._value("mileage", "Нет данных"), "info"]' in source
    assert '<strong>${this._escape(meta[2])}</strong>' in source
    assert "white-space:normal" in source
    assert "overflow:visible" in source


def test_headlights_remain_decoupled_from_engine_state() -> None:
    source = _source()
    assert 'class="headlights"' in source
    assert ".headlight-beam{fill:transparent;opacity:0}" in source
    assert "engine-on .headlights" not in source
