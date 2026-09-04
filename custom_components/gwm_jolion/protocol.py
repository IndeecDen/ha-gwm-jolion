"""Protocol metadata for GWM Jolion telemetry.

This module is intentionally dependency-free so protocol metadata can be tested
without importing Home Assistant.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class VerificationStatus(StrEnum):
    """How confidently a GWM signal is understood."""

    CONFIRMED = "confirmed"
    IMPLEMENTED = "implemented"
    KNOWN_UNVERIFIED = "known_unverified"
    EXPERIMENTAL = "experimental"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class SignalInfo:
    """Human-readable metadata for one GWM telemetry code."""

    code: str
    key: str
    description: str
    status: VerificationStatus
    notes: str = ""


SIGNALS: dict[str, SignalInfo] = {
    "2011007": SignalInfo("2011007", "range_km", "Запас хода", VerificationStatus.CONFIRMED),
    "2017002": SignalInfo("2017002", "fuel_liters", "Количество топлива", VerificationStatus.CONFIRMED),
    "2103010": SignalInfo("2103010", "mileage_total", "Общий пробег", VerificationStatus.CONFIRMED),
    "2101001": SignalInfo("2101001", "tire_fl_pressure", "Давление шины 1", VerificationStatus.IMPLEMENTED),
    "2101002": SignalInfo("2101002", "tire_fr_pressure", "Давление шины 2", VerificationStatus.IMPLEMENTED),
    "2101003": SignalInfo("2101003", "tire_rl_pressure", "Давление шины 3", VerificationStatus.IMPLEMENTED),
    "2101004": SignalInfo("2101004", "tire_rr_pressure", "Давление шины 4", VerificationStatus.IMPLEMENTED),
    "2101005": SignalInfo("2101005", "tire_fl_temp", "Температура шины 1", VerificationStatus.IMPLEMENTED),
    "2101006": SignalInfo("2101006", "tire_fr_temp", "Температура шины 2", VerificationStatus.IMPLEMENTED),
    "2101007": SignalInfo("2101007", "tire_rl_temp", "Температура шины 3", VerificationStatus.IMPLEMENTED),
    "2101008": SignalInfo("2101008", "tire_rr_temp", "Температура шины 4", VerificationStatus.IMPLEMENTED),
    "2102001": SignalInfo("2102001", "tpms_pressure_fl_raw", "TPMS pressure status 1", VerificationStatus.KNOWN_UNVERIFIED),
    "2102002": SignalInfo("2102002", "tpms_pressure_fr_raw", "TPMS pressure status 2", VerificationStatus.KNOWN_UNVERIFIED),
    "2102003": SignalInfo("2102003", "tpms_pressure_rl_raw", "TPMS pressure status 3", VerificationStatus.KNOWN_UNVERIFIED),
    "2102004": SignalInfo("2102004", "tpms_pressure_rr_raw", "TPMS pressure status 4", VerificationStatus.KNOWN_UNVERIFIED),
    "2102007": SignalInfo("2102007", "tpms_temp_fl_raw", "TPMS temperature status 1", VerificationStatus.KNOWN_UNVERIFIED),
    "2102008": SignalInfo("2102008", "tpms_temp_fr_raw", "TPMS temperature status 2", VerificationStatus.KNOWN_UNVERIFIED),
    "2102009": SignalInfo("2102009", "tpms_temp_rl_raw", "TPMS temperature status 3", VerificationStatus.KNOWN_UNVERIFIED),
    "2102010": SignalInfo("2102010", "tpms_temp_rr_raw", "TPMS temperature status 4", VerificationStatus.KNOWN_UNVERIFIED),
    "2016001": SignalInfo("2016001", "engine_state_raw", "Состояние двигателя", VerificationStatus.CONFIRMED, "0=OFF, 2=RUNNING на тестовом Jolion"),
    "2208001": SignalInfo("2208001", "central_lock_raw", "Центральный замок", VerificationStatus.CONFIRMED, "0=locked, 1=unlocked"),
    "2206001": SignalInfo("2206001", "trunk_raw", "Багажник", VerificationStatus.CONFIRMED, "0=closed, 1=open"),
    "2206002": SignalInfo("2206002", "door_front_left_raw", "Дверь, код 2206002", VerificationStatus.CONFIRMED, "0=closed, 1=open; физическая позиция требует дополнительной сверки"),
    "2206003": SignalInfo("2206003", "door_rear_left_raw", "Дверь, код 2206003", VerificationStatus.CONFIRMED, "0=closed, 1=open; физическая позиция требует дополнительной сверки"),
    "2206004": SignalInfo("2206004", "door_front_right_raw", "Дверь, код 2206004", VerificationStatus.CONFIRMED, "0=closed, 1=open; физическая позиция требует дополнительной сверки"),
    "2206005": SignalInfo("2206005", "door_rear_right_raw", "Дверь, код 2206005", VerificationStatus.CONFIRMED, "0=closed, 1=open; физическая позиция требует дополнительной сверки"),
    "2210001": SignalInfo("2210001", "window_2210001_raw", "Окно 2210001", VerificationStatus.CONFIRMED, "1=closed, 0=open; позиция требует дополнительной сверки"),
    "2210002": SignalInfo("2210002", "window_2210002_raw", "Окно 2210002", VerificationStatus.CONFIRMED, "1=closed, 0=open; позиция требует дополнительной сверки"),
    "2210003": SignalInfo("2210003", "window_2210003_raw", "Окно 2210003", VerificationStatus.CONFIRMED, "1=closed, 0=open; позиция требует дополнительной сверки"),
    "2210004": SignalInfo("2210004", "window_2210004_raw", "Окно 2210004", VerificationStatus.CONFIRMED, "1=closed, 0=open; позиция требует дополнительной сверки"),
    "2210010": SignalInfo("2210010", "window_learn_2210010_raw", "Статус обучения стеклоподъёмника 2210010", VerificationStatus.KNOWN_UNVERIFIED),
    "2210011": SignalInfo("2210011", "window_learn_2210011_raw", "Статус обучения стеклоподъёмника 2210011", VerificationStatus.KNOWN_UNVERIFIED),
    "2210012": SignalInfo("2210012", "window_learn_2210012_raw", "Статус обучения стеклоподъёмника 2210012", VerificationStatus.KNOWN_UNVERIFIED),
    "2210013": SignalInfo("2210013", "window_learn_2210013_raw", "Статус обучения стеклоподъёмника 2210013", VerificationStatus.KNOWN_UNVERIFIED),
    "2202001": SignalInfo("2202001", "climate_raw", "Состояние климатической системы", VerificationStatus.EXPERIMENTAL, "Предполагается 0=OFF, 1=ON"),
    "2220001": SignalInfo("2220001", "driver_seat_heat_level_raw", "Уровень подогрева водительского сиденья", VerificationStatus.KNOWN_UNVERIFIED),
    "2220002": SignalInfo("2220002", "passenger_seat_heat_level_raw", "Уровень подогрева пассажирского сиденья", VerificationStatus.KNOWN_UNVERIFIED),
    "2310001": SignalInfo("2310001", "gps_authorized_raw", "GPS authorization", VerificationStatus.KNOWN_UNVERIFIED),
    "4105008": SignalInfo("4105008", "tbox_signal_raw", "Уровень сотового сигнала T-Box", VerificationStatus.KNOWN_UNVERIFIED),
    "2204007": SignalInfo("2204007", "light_2204007_raw", "Световой статус 2204007", VerificationStatus.KNOWN_UNVERIFIED),
    "2204008": SignalInfo("2204008", "light_2204008_raw", "Неопределённый световой статус 2204008", VerificationStatus.UNKNOWN),
    "2204009": SignalInfo("2204009", "left_indicator_raw", "Левый указатель поворота", VerificationStatus.KNOWN_UNVERIFIED),
    "2204010": SignalInfo("2204010", "right_indicator_raw", "Правый указатель поворота", VerificationStatus.KNOWN_UNVERIFIED),
    "2222001": SignalInfo("2222001", "front_defrost_raw", "Передний defrost / обдув лобового", VerificationStatus.EXPERIMENTAL),
    "2210032": SignalInfo("2210032", "rear_defrost_raw", "Обогрев заднего стекла", VerificationStatus.KNOWN_UNVERIFIED),
    "2060016": SignalInfo("2060016", "steering_wheel_heat_raw", "Обогрев руля", VerificationStatus.KNOWN_UNVERIFIED),
    "2202111": SignalInfo("2202111", "front_windscreen_heat_raw", "Электрообогрев лобового стекла", VerificationStatus.KNOWN_UNVERIFIED),
    "2078020": SignalInfo("2078020", "air_circulation_raw", "Очистка/циркуляция воздуха салона", VerificationStatus.KNOWN_UNVERIFIED),
}


def signal_report(seen_codes: set[str] | list[str] | tuple[str, ...]) -> dict[str, dict[str, str | bool]]:
    """Build a serialisable report for observed protocol codes."""
    seen = {str(code) for code in seen_codes}
    report: dict[str, dict[str, str | bool]] = {}
    for code, info in SIGNALS.items():
        report[code] = {
            "key": info.key,
            "description": info.description,
            "status": info.status.value,
            "observed": code in seen,
            "notes": info.notes,
        }
    return report
