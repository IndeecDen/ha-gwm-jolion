"""Constants for the GWM Jolion integration."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

DOMAIN = "gwm_jolion"
VERSION = "0.1.0-beta.1"
PLATFORMS = ["button", "sensor", "binary_sensor", "device_tracker", "lock", "climate", "number"]

CONF_PHONE = "phone"
CONF_COUNTRY = "country"
CONF_COUNTRY_CODE = "country_code"
CONF_DEVICE_ID = "device_id"
CONF_POLL_INTERVAL = "poll_interval"
CONF_ENABLE_REMOTE_CONTROLS = "enable_remote_controls"
CONF_COMMAND_COOLDOWN = "command_cooldown_seconds"
CONF_SECURITY_PIN = "security_pin"

DEFAULT_COUNTRY = "RU"
DEFAULT_COUNTRY_CODE = "+7"
DEFAULT_POLL_INTERVAL = 300
DEFAULT_ENABLE_REMOTE_CONTROLS = False
DEFAULT_COMMAND_COOLDOWN = 30

DEFAULT_CLIMATE_TEMPERATURE = 22
DEFAULT_CLIMATE_RUNTIME = 15
MIN_CLIMATE_TEMPERATURE = 16
MAX_CLIMATE_TEMPERATURE = 32
MIN_CLIMATE_RUNTIME = 5
MAX_CLIMATE_RUNTIME = 30

BASE_URL = "https://rus-h5-gateway.gwmcloud.com"
AUTH_PREFIX = "gwm"
APP_ID = "1"
BRAND = "1"
TERMINAL = "GW_APP_Haval"
ENTERPRISE_ID = "CC01"
SYSTEM_TYPE = "1"
APP_VERSION = "2.2.3"
LANGUAGE = "ru"
REGION_CODE = "RU"
COUNTRY = "RU"
APP_KEY = "4694605273"
APP_SEC = "e4e478c00f570e76a8993653a7b81d57"

ENDPOINT_LOGIN = "/app-api/api/v1.0/userAuth/loginAccount"
ENDPOINT_VEHICLES = "/app-api/api/v1.0/vehicle/acquireVehicles"
ENDPOINT_LAST_STATUS = "/app-api/api/v1.0/vehicle/getLastStatus"
ENDPOINT_FIND_STATUS = "/app-api/api/v1.0/vehicle/findStatus"
ENDPOINT_VEHICLE_BASICS_INFO = "/app-api/api/v1.0/vehicle/vehicleBasicsInfo"
ENDPOINT_MODIFY_REMOTE_CTL_INFO = "/app-api/api/v1.0/vehicle/modifyVehicleRemoteCtlInfo"
ENDPOINT_T5_SEND_CMD = "/app-api/api/v1.0/vehicle/T5/sendCmd"
ENDPOINT_T5_CTRL_RESULT = "/app-api/api/v1.0/vehicle/getRemoteCtrlResultT5"
ENDPOINT_CHECK_SECURITY_PASSWORD = "/app-api/api/v1.0/userAuth/checkSecurityPassword"

KPA_TO_BAR = 100.0


class Conversion(Enum):
    PRESSURE_KPA_TO_BAR = "pressure_kpa_to_bar"


@dataclass(frozen=True)
class SensorDef:
    key: str
    name: str
    unit: str | None = None
    icon: str | None = None
    device_class: str | None = None
    code: str | None = None
    convert: Conversion | None = None
    diagnostic: bool = False


# Normal user-facing numeric telemetry.
ITEM_MAP: dict[str, SensorDef] = {
    "2011007": SensorDef("range_km", "Запас хода", "km", "mdi:map-marker-distance", code="2011007"),
    "2017002": SensorDef("fuel_liters", "Топливо", "L", "mdi:fuel", code="2017002"),
    "2103010": SensorDef("mileage_total", "Пробег", "km", "mdi:counter", code="2103010"),
    "2101001": SensorDef("tire_fl_pressure", "Давление: переднее левое", "bar", "mdi:car-tire-alert", "pressure", "2101001", Conversion.PRESSURE_KPA_TO_BAR),
    "2101002": SensorDef("tire_fr_pressure", "Давление: переднее правое", "bar", "mdi:car-tire-alert", "pressure", "2101002", Conversion.PRESSURE_KPA_TO_BAR),
    "2101003": SensorDef("tire_rl_pressure", "Давление: заднее левое", "bar", "mdi:car-tire-alert", "pressure", "2101003", Conversion.PRESSURE_KPA_TO_BAR),
    "2101004": SensorDef("tire_rr_pressure", "Давление: заднее правое", "bar", "mdi:car-tire-alert", "pressure", "2101004", Conversion.PRESSURE_KPA_TO_BAR),
    "2101005": SensorDef("tire_fl_temp", "Температура шины: передняя левая", "°C", "mdi:thermometer", "temperature", "2101005"),
    "2101006": SensorDef("tire_fr_temp", "Температура шины: передняя правая", "°C", "mdi:thermometer", "temperature", "2101006"),
    "2101007": SensorDef("tire_rl_temp", "Температура шины: задняя левая", "°C", "mdi:thermometer", "temperature", "2101007"),
    "2101008": SensorDef("tire_rr_temp", "Температура шины: задняя правая", "°C", "mdi:thermometer", "temperature", "2101008"),
}

# Raw values are retained in coordinator state for protocol capture, card
# attributes and future research.  alpha.20 no longer exposes this whole table
# as Home Assistant sensor entities; entity_surface.py whitelists the two useful
# seat-heater level sensors.
RAW_SENSOR_MAP: dict[str, SensorDef] = {
    "2102001": SensorDef("tpms_pressure_fl_raw", "TPMS давление FL (raw)", icon="mdi:car-tire-alert", code="2102001", diagnostic=True),
    "2102002": SensorDef("tpms_pressure_fr_raw", "TPMS давление FR (raw)", icon="mdi:car-tire-alert", code="2102002", diagnostic=True),
    "2102003": SensorDef("tpms_pressure_rl_raw", "TPMS давление RL (raw)", icon="mdi:car-tire-alert", code="2102003", diagnostic=True),
    "2102004": SensorDef("tpms_pressure_rr_raw", "TPMS давление RR (raw)", icon="mdi:car-tire-alert", code="2102004", diagnostic=True),
    "2102007": SensorDef("tpms_temp_fl_raw", "TPMS температура FL (raw)", icon="mdi:thermometer-alert", code="2102007", diagnostic=True),
    "2102008": SensorDef("tpms_temp_fr_raw", "TPMS температура FR (raw)", icon="mdi:thermometer-alert", code="2102008", diagnostic=True),
    "2102009": SensorDef("tpms_temp_rl_raw", "TPMS температура RL (raw)", icon="mdi:thermometer-alert", code="2102009", diagnostic=True),
    "2102010": SensorDef("tpms_temp_rr_raw", "TPMS температура RR (raw)", icon="mdi:thermometer-alert", code="2102010", diagnostic=True),
    "2210001": SensorDef("window_2210001_raw", "Окно переднее левое (raw)", icon="mdi:car-door", code="2210001", diagnostic=True),
    "2210002": SensorDef("window_2210002_raw", "Окно переднее правое (raw)", icon="mdi:car-door", code="2210002", diagnostic=True),
    "2210003": SensorDef("window_2210003_raw", "Окно заднее левое (raw)", icon="mdi:car-door", code="2210003", diagnostic=True),
    "2210004": SensorDef("window_2210004_raw", "Окно заднее правое (raw)", icon="mdi:car-door", code="2210004", diagnostic=True),
    "2210010": SensorDef("window_learn_2210010_raw", "Обучение стекла 2210010 (raw)", icon="mdi:car-door", code="2210010", diagnostic=True),
    "2210011": SensorDef("window_learn_2210011_raw", "Обучение стекла 2210011 (raw)", icon="mdi:car-door", code="2210011", diagnostic=True),
    "2210012": SensorDef("window_learn_2210012_raw", "Обучение стекла 2210012 (raw)", icon="mdi:car-door", code="2210012", diagnostic=True),
    "2210013": SensorDef("window_learn_2210013_raw", "Обучение стекла 2210013 (raw)", icon="mdi:car-door", code="2210013", diagnostic=True),
    "2220001": SensorDef("driver_seat_heat_level_raw", "Подогрев сиденья водителя", icon="mdi:car-seat-heater", code="2220001"),
    "2220002": SensorDef("passenger_seat_heat_level_raw", "Подогрев сиденья пассажира", icon="mdi:car-seat-heater", code="2220002"),
    "2204007": SensorDef("light_2204007_raw", "Свет 2204007 (raw)", icon="mdi:car-light-high", code="2204007", diagnostic=True),
    "2204008": SensorDef("light_2204008_raw", "Дальний свет 2204008 (raw, кандидат)", icon="mdi:car-light-high", code="2204008", diagnostic=True),
    "2204009": SensorDef("left_indicator_raw", "Левый указатель поворота (raw)", icon="mdi:arrow-left-bold", code="2204009", diagnostic=True),
    "2204010": SensorDef("right_indicator_raw", "Правый указатель поворота (raw)", icon="mdi:arrow-right-bold", code="2204010", diagnostic=True),
    "4105008": SensorDef("tbox_signal_raw", "Уровень сигнала T-Box (raw)", icon="mdi:signal", code="4105008", diagnostic=True),
}

VEHICLE_STATUS_MAP: dict[str, str] = {
    "2206001": "trunk_raw",
    "2206002": "door_front_left_raw",
    "2206003": "door_rear_left_raw",
    "2206004": "door_front_right_raw",
    "2206005": "door_rear_right_raw",
    "2210001": "window_2210001_raw",
    "2210002": "window_2210002_raw",
    "2210003": "window_2210003_raw",
    "2210004": "window_2210004_raw",
    "2208001": "central_lock_raw",
    "2016001": "engine_state_raw",
    "2202001": "climate_raw",
    "2310001": "gps_authorized_raw",
    "2222001": "front_defrost_raw",
    "2210032": "rear_defrost_raw",
    "2060016": "steering_wheel_heat_raw",
    "2202111": "front_windscreen_heat_raw",
    "2078020": "air_circulation_raw",
}

# Only derived metadata that is genuinely useful as a standalone entity.
EXTRA_SENSORS: dict[str, SensorDef] = {
    "fuel_percent": SensorDef("fuel_percent", "Уровень топлива", "%", "mdi:fuel"),
}

# Public binary states.  Raw/unconfirmed helper states stay in coordinator.data
# and diagnostics instead of generating entity-registry noise.
BINARY_SENSOR_DEFS = (
    ("tbox_online", "T-Box онлайн", "connectivity", False),
    ("engine_running", "Двигатель работает", "running", False),
    ("doors_open", "Двери открыты", "door", False),
    ("door_front_left_open", "Дверь передняя левая", "door", False),
    ("door_rear_left_open", "Дверь задняя левая", "door", False),
    ("door_front_right_open", "Дверь передняя правая", "door", False),
    ("door_rear_right_open", "Дверь задняя правая", "door", False),
    ("windows_open", "Окна открыты", "window", False),
    ("window_2210001_open", "Окно переднее левое", "window", False),
    ("window_2210002_open", "Окно переднее правое", "window", False),
    ("window_2210003_open", "Окно заднее левое", "window", False),
    ("window_2210004_open", "Окно заднее правое", "window", False),
    ("trunk_open", "Багажник открыт", "door", False),
    ("climate_on", "Климат работает", "running", False),
)
