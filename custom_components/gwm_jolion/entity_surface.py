"""Curated Home Assistant entity surface for GWM Jolion.

Protocol discovery keeps collecting raw values internally.  This module only
controls which of those values become Home Assistant entities.
"""

from __future__ import annotations

# Raw telemetry that is useful enough to expose as a normal user-facing sensor.
# The unique IDs intentionally stay stable even though the friendly names no
# longer say "raw".
PUBLIC_RAW_SENSOR_CODES: tuple[str, ...] = (
    "2220001",  # driver seat heat level
    "2220002",  # passenger seat heat level
)

# Derived/metadata sensors that are useful in dashboards and automations.
PUBLIC_EXTRA_SENSOR_KEYS: tuple[str, ...] = (
    "fuel_percent",
)

# Command buttons that add a useful action not already represented by a better
# native Home Assistant entity.  Lock/unlock are intentionally omitted because
# lock.central_lock is the canonical control.  Window movement is omitted until
# the T5 0x08 payload is physically re-confirmed.
PUBLIC_COMMAND_BUTTON_KEYS: frozenset[str] = frozenset(
    {
        "start_engine",
        "stop_engine",
        "flash_lights",
        "horn",
        "flash_and_horn",
        "open_trunk",
        "close_trunk",
        "rear_defrost_on",
        "rear_defrost_off",
        "steering_wheel_heat_on",
        "steering_wheel_heat_off",
    }
)

# Optional equipment that currently has a useful public entity or a physically
# useful command.  Experimental/discovery-only options stay in protocol metadata
# but no longer clutter the normal Options Flow.
PUBLIC_MANUAL_CAPABILITIES: frozenset[str] = frozenset(
    {
        "steering_wheel_heat",
        "rear_defrost",
        "seat_heat_driver",
        "seat_heat_passenger",
    }
)

# Entity unique-id suffixes removed during the v1 -> v2 config-entry migration.
# Public seat/window entities are included where they must be recreated to drop
# the old diagnostic/raw presentation.
MIGRATION_REMOVE_ENTITY_SUFFIXES: dict[str, tuple[str, ...]] = {
    "sensor": (
        # old raw protocol entities
        "tpms_pressure_fl_raw",
        "tpms_pressure_fr_raw",
        "tpms_pressure_rl_raw",
        "tpms_pressure_rr_raw",
        "tpms_temp_fl_raw",
        "tpms_temp_fr_raw",
        "tpms_temp_rl_raw",
        "tpms_temp_rr_raw",
        "window_2210001_raw",
        "window_2210002_raw",
        "window_2210003_raw",
        "window_2210004_raw",
        "window_learn_2210010_raw",
        "window_learn_2210011_raw",
        "window_learn_2210012_raw",
        "window_learn_2210013_raw",
        "light_2204007_raw",
        "light_2204008_raw",
        "left_indicator_raw",
        "right_indicator_raw",
        "tbox_signal_raw",
        # recreated with clean user-facing names/category
        "driver_seat_heat_level_raw",
        "passenger_seat_heat_level_raw",
        # duplicated/diagnostic metadata entities
        "brand",
        "model",
        "color",
        "engine_type",
        "tank_capacity_l",
        "vehicle_config",
        "vehicle_type",
        "telematics_platform",
        "model_code_raw",
        "oil_qty",
        "service_status",
        "tbox_status",
        "climate_saved_temperature",
        "climate_saved_runtime",
        "engine_saved_runtime",
        "seat_heat_saved_runtime",
        "seat_heating_type_raw",
        "front_defrost_status_basics_raw",
        "rear_defrost_status_basics_raw",
        "air_purifier_status_raw",
        "purifier_runtime",
        # diagnostic helper entities folded into attributes/diagnostics
        "last_command",
        "last_command_time",
        "unknown_signal_count",
        "vehicle_basics_status",
        "feature_flags",
        "protocol_capture_status",
    ),
    "binary_sensor": (
        # recreated as normal user-facing window entities
        "window_2210001_open",
        "window_2210002_open",
        "window_2210003_open",
        "window_2210004_open",
        # duplicated/unconfirmed status entities
        "vehicle_unlocked",
        "gps_authorized",
        "front_defrost_on",
        "rear_defrost_on",
        "steering_wheel_heat_on",
        "front_windscreen_heat_on",
        "air_circulation_on",
    ),
    "button": (
        # canonical lock entity replaces these two buttons
        "cmd_lock_vehicle",
        "cmd_unlock_vehicle",
        # physically unconfirmed/experimental commands are not public buttons
        "cmd_close_windows",
        "cmd_open_windows",
        "cmd_close_sunroof",
        "cmd_open_sunroof",
        "cmd_open_sunshade",
        "cmd_close_sunshade",
        "cmd_front_defrost_on",
        "cmd_front_defrost_off",
        "cmd_cabin_clean",
    ),
}

# Old Options Flow keys removed from the config entry in the same migration.
OBSOLETE_OPTION_KEYS: frozenset[str] = frozenset(
    {
        "feature_sunroof",
        "feature_sunshade",
        "feature_front_defrost",
        "feature_front_windscreen_heat",
        "feature_cabin_clean",
        "feature_air_purifier",
    }
)
