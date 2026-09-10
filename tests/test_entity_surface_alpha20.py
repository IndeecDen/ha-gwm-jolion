from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_public_entity_surface_is_curated() -> None:
    surface = _load("gwm_entity_surface_alpha20", "custom_components/gwm_jolion/entity_surface.py")
    assert surface.PUBLIC_RAW_SENSOR_CODES == ("2220001", "2220002")
    assert surface.PUBLIC_EXTRA_SENSOR_KEYS == ("fuel_percent",)

    assert "lock_vehicle" not in surface.PUBLIC_COMMAND_BUTTON_KEYS
    assert "unlock_vehicle" not in surface.PUBLIC_COMMAND_BUTTON_KEYS
    assert "close_windows" not in surface.PUBLIC_COMMAND_BUTTON_KEYS
    assert "open_windows" not in surface.PUBLIC_COMMAND_BUTTON_KEYS
    assert "front_defrost_on" not in surface.PUBLIC_COMMAND_BUTTON_KEYS
    assert "open_sunroof" not in surface.PUBLIC_COMMAND_BUTTON_KEYS

    assert "start_engine" in surface.PUBLIC_COMMAND_BUTTON_KEYS
    assert "stop_engine" in surface.PUBLIC_COMMAND_BUTTON_KEYS
    assert "open_trunk" in surface.PUBLIC_COMMAND_BUTTON_KEYS
    assert "rear_defrost_on" not in surface.PUBLIC_COMMAND_BUTTON_KEYS
    assert "steering_wheel_heat_on" not in surface.PUBLIC_COMMAND_BUTTON_KEYS


def test_binary_surface_has_only_reliable_status_entities() -> None:
    const = _load("gwm_const_entity_surface_alpha20", "custom_components/gwm_jolion/const.py")
    keys = {key for key, _name, _device_class, _diagnostic in const.BINARY_SENSOR_DEFS}
    assert keys == {
        "tbox_online",
        "engine_running",
        "doors_open",
        "door_front_left_open",
        "door_rear_left_open",
        "door_front_right_open",
        "door_rear_right_open",
        "windows_open",
        "window_2210001_open",
        "window_2210002_open",
        "window_2210003_open",
        "window_2210004_open",
        "trunk_open",
        "climate_on",
    }
    assert all(not diagnostic for _key, _name, _device_class, diagnostic in const.BINARY_SENSOR_DEFS)

    # Raw telemetry remains available internally for capture/protocol work.
    assert "2204008" in const.RAW_SENSOR_MAP
    assert "4105008" in const.RAW_SENSOR_MAP
    assert "2210010" in const.RAW_SENSOR_MAP


def test_seat_heat_is_a_clean_public_sensor_not_raw_entity_noise() -> None:
    const = _load("gwm_const_seats_alpha20", "custom_components/gwm_jolion/const.py")
    assert const.RAW_SENSOR_MAP["2220001"].name == "Подогрев сиденья водителя"
    assert const.RAW_SENSOR_MAP["2220002"].name == "Подогрев сиденья пассажира"
    assert const.RAW_SENSOR_MAP["2220001"].diagnostic is False
    assert const.RAW_SENSOR_MAP["2220002"].diagnostic is False

    sensor_source = (ROOT / "custom_components/gwm_jolion/sensor.py").read_text(encoding="utf-8")
    assert "PUBLIC_RAW_SENSOR_CODES" in sensor_source
    assert "list(RAW_SENSOR_MAP.values())" not in sensor_source
    assert "GwmJolionUnknownSignalsSensor" not in sensor_source
    assert "GwmJolionProtocolCaptureSensor" not in sensor_source
    assert "GwmJolionFeatureFlagsSensor" not in sensor_source


def test_v2_migration_removes_old_registry_noise() -> None:
    surface = _load("gwm_entity_surface_migration_alpha20", "custom_components/gwm_jolion/entity_surface.py")
    sensor_suffixes = set(surface.MIGRATION_REMOVE_ENTITY_SUFFIXES["sensor"])
    binary_suffixes = set(surface.MIGRATION_REMOVE_ENTITY_SUFFIXES["binary_sensor"])
    button_suffixes = set(surface.MIGRATION_REMOVE_ENTITY_SUFFIXES["button"])

    assert "window_learn_2210010_raw" in sensor_suffixes
    assert "tbox_signal_raw" in sensor_suffixes
    assert "feature_flags" in sensor_suffixes
    assert "protocol_capture_status" in sensor_suffixes
    assert "vehicle_unlocked" in binary_suffixes
    assert "gps_authorized" in binary_suffixes
    assert "rear_defrost_on" in binary_suffixes
    assert "cmd_lock_vehicle" in button_suffixes
    assert "cmd_close_windows" in button_suffixes

    init_source = (ROOT / "custom_components/gwm_jolion/__init__.py").read_text(encoding="utf-8")
    config_source = (ROOT / "custom_components/gwm_jolion/config_flow.py").read_text(encoding="utf-8")
    assert "async def async_migrate_entry" in init_source
    assert "CONFIG_ENTRY_VERSION = 2" in init_source
    assert "VERSION = 2" in config_source


def test_alpha20_frontend_uses_clean_entity_attributes() -> None:
    patch = (ROOT / "custom_components/gwm_jolion/frontend/gwm-jolion-alpha20.js").read_text(encoding="utf-8")
    init_source = (ROOT / "custom_components/gwm_jolion/__init__.py").read_text(encoding="utf-8")

    assert 'const VERSION = "0.1.0-beta.3"' in patch
    assert 'signal_level_raw' in patch
    assert 'feature_flags' in patch
    assert 'last_successful_update' in patch
    assert 'if (id === "windows") return ""' not in patch
    assert 'entities.windowFl = oldFr' in patch
    assert 'entities.windowFr = oldFl' in patch
    assert 'gwm-jolion-alpha20.js?v=0.1.0-beta.3' in init_source
