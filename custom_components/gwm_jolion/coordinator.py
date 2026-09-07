"""Data coordinator and remote-command manager for GWM Jolion."""

from __future__ import annotations

import asyncio
import copy
from datetime import datetime, timedelta, timezone
import logging
import time
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import GwmJolionApiClient, GwmJolionApiError
from .capabilities import CAPABILITIES, capability_for_command, capability_report
from .command_safety import remote_start_block_reason
from .commands import COMMANDS, UNSUPPORTED_COMMANDS, build_seat_heating_instructions
from .const import DEFAULT_CLIMATE_RUNTIME, DEFAULT_CLIMATE_TEMPERATURE, DOMAIN, VERSION
from .protocol import SIGNALS, VerificationStatus, update_signal_change_history
from .protocol_capture import (
    append_jsonl,
    build_capture_record,
    build_marker_record,
    normalize_marker,
)

_LOGGER = logging.getLogger(__name__)


def _set_nested(data: dict[str, Any], path: tuple[str, ...], value: Any) -> None:
    node: dict[str, Any] = data
    for key in path[:-1]:
        child = node.get(key)
        if not isinstance(child, dict):
            raise HomeAssistantError(f"Invalid command template path: {path}")
        node = child
    node[path[-1]] = value


def _friendly_remote_error(err: Exception) -> str:
    """Return a concise user-facing command error without hiding GWM details."""
    if isinstance(err, GwmJolionApiError):
        if err.code == "timeout":
            return "GWM не подтвердил выполнение команды за 300 секунд"
        if err.code:
            return f"{err} (код GWM {err.code})"
    text = str(err).strip()
    return text or "Неизвестная ошибка удалённой команды"


class GwmJolionCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinate polling, diagnostics, protocol capture and remote commands."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: GwmJolionApiClient,
        poll_interval: int,
        entry_id: str,
        *,
        enable_remote_controls: bool,
        command_cooldown: int,
        security_pin: str | None,
        feature_flags: dict[str, bool] | None = None,
        protocol_capture_enabled: bool = False,
        protocol_capture_path: str | None = None,
    ) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=timedelta(seconds=poll_interval))
        self.client = client
        self.entry_id = entry_id
        self.enable_remote_controls = enable_remote_controls
        self.command_cooldown = command_cooldown
        self.security_pin = security_pin
        self.feature_flags = dict(feature_flags or {})
        self.protocol_capture_enabled = protocol_capture_enabled
        self.protocol_capture_path = protocol_capture_path
        self.protocol_capture_sequence = 0
        self.protocol_capture_last_error: str | None = None
        self.protocol_capture_last_record_time: datetime | None = None
        self.protocol_capture_last_source: str | None = None
        self.protocol_capture_last_changes_count: int | None = None
        self.protocol_capture_last_marker: str | None = None
        self._protocol_capture_last_signals: dict[str, Any] = {}
        self._protocol_capture_last_basics: dict[str, Any] = {}
        self._protocol_capture_last_status_meta: dict[str, Any] = {}
        self._protocol_capture_last_tbox_meta: dict[str, Any] = {}
        self._protocol_capture_has_snapshot = False
        self._next_update_source = "poll"
        self._last_command_time = 0.0
        self._command_lock = asyncio.Lock()
        self.climate_target_temperature = DEFAULT_CLIMATE_TEMPERATURE
        self.climate_operation_time = DEFAULT_CLIMATE_RUNTIME
        self.last_command_name: str | None = None
        self.last_command_status: str | None = None
        self.last_command_result_code: str | None = None
        self.last_command_result_message: str | None = None
        self.last_command_at: datetime | None = None
        self.last_successful_update: datetime | None = None
        self.unknown_signal_history: dict[str, dict[str, Any]] = {}
        self.signal_change_history: list[dict[str, Any]] = []
        self._signal_history_last_values: dict[str, Any] = {}
        self.seen_signal_codes: set[str] = set()

    async def _async_update_data(self) -> dict[str, Any]:
        source = self._next_update_source
        self._next_update_source = "poll"
        data = await self.client.async_update()
        now = datetime.now(timezone.utc)
        state = data.get("state") or {}
        seen = state.get("_seen_signals") or {}
        raw_unknown = state.get("_unknown_signals") or {}
        unknown_for_history: dict[str, Any] = (
            dict(raw_unknown) if isinstance(raw_unknown, dict) else {}
        )
        signals_for_change_history: dict[str, Any] = {}

        if isinstance(seen, dict):
            signals_for_change_history.update({str(code): value for code, value in seen.items()})
            self.seen_signal_codes.update(str(code) for code in seen)
            for raw_code, value in seen.items():
                code = str(raw_code)
                info = SIGNALS.get(code)
                if info is not None and info.status == VerificationStatus.UNKNOWN:
                    unknown_for_history.setdefault(code, value)

        if isinstance(raw_unknown, dict):
            for raw_code, value in raw_unknown.items():
                signals_for_change_history.setdefault(str(raw_code), value)

        if signals_for_change_history:
            update_signal_change_history(
                self.signal_change_history,
                self._signal_history_last_values,
                signals_for_change_history,
                now.isoformat(),
            )

        if unknown_for_history:
            self._track_unknown_signals(unknown_for_history, now)

        if self.protocol_capture_enabled and self.protocol_capture_path:
            await self._async_capture_protocol_update(
                timestamp=now,
                source=source,
                signals=signals_for_change_history,
                unknown_signals=unknown_for_history,
                vehicle_basics=data.get("vehicle_basics") or {},
                signal_units=state.get("_signal_units") or {},
                signal_item_seen_keys=state.get("_signal_item_seen_keys") or [],
                status_meta=state.get("_status_meta") or {},
                status_structure=state.get("_status_structure") or {},
                tbox_meta=state.get("_tbox_meta") or {},
                tbox_structure=state.get("_tbox_structure") or {},
                vehicle_basics_seen_keys=state.get("_vehicle_basics_seen_keys") or [],
                vehicle_basics_structure=state.get("_vehicle_basics_structure") or {},
            )

        self.last_successful_update = now
        return data

    async def _async_capture_protocol_update(
        self,
        *,
        timestamp: datetime,
        source: str,
        signals: dict[str, Any],
        unknown_signals: dict[str, Any],
        vehicle_basics: dict[str, Any],
        signal_units: dict[str, Any],
        signal_item_seen_keys: list[str],
        status_meta: dict[str, Any],
        status_structure: dict[str, Any],
        tbox_meta: dict[str, Any],
        tbox_structure: dict[str, Any],
        vehicle_basics_seen_keys: list[str],
        vehicle_basics_structure: dict[str, Any],
    ) -> None:
        """Append one successful cloud update to the active JSONL capture."""
        normalized_signals = {str(code): value for code, value in signals.items()}
        normalized_unknown = {str(code): value for code, value in unknown_signals.items()}
        normalized_basics = (
            {str(key): value for key, value in vehicle_basics.items()}
            if isinstance(vehicle_basics, dict)
            else {}
        )
        normalized_status_meta = (
            {str(key): value for key, value in status_meta.items()}
            if isinstance(status_meta, dict)
            else {}
        )
        normalized_tbox_meta = (
            {str(key): value for key, value in tbox_meta.items()}
            if isinstance(tbox_meta, dict)
            else {}
        )
        sequence = self.protocol_capture_sequence + 1
        baseline = not self._protocol_capture_has_snapshot
        record = build_capture_record(
            sequence=sequence,
            timestamp=timestamp,
            source=source,
            integration_version=VERSION,
            signals=normalized_signals,
            previous_signals=self._protocol_capture_last_signals,
            unknown_signals=normalized_unknown,
            vehicle_basics=normalized_basics,
            previous_vehicle_basics=self._protocol_capture_last_basics,
            baseline=baseline,
            signal_units=signal_units,
            signal_item_seen_keys=signal_item_seen_keys,
            status_meta=normalized_status_meta,
            previous_status_meta=self._protocol_capture_last_status_meta,
            status_structure=status_structure,
            tbox_meta=normalized_tbox_meta,
            previous_tbox_meta=self._protocol_capture_last_tbox_meta,
            tbox_structure=tbox_structure,
            vehicle_basics_seen_keys=vehicle_basics_seen_keys,
            vehicle_basics_structure=vehicle_basics_structure,
        )
        try:
            await self.hass.async_add_executor_job(
                append_jsonl,
                self.protocol_capture_path,
                record,
            )
        except Exception as err:  # capture must never break vehicle polling
            self.protocol_capture_last_error = str(err)
            _LOGGER.warning("Cannot append GWM protocol capture: %s", err)
            return

        self.protocol_capture_sequence = sequence
        self.protocol_capture_last_error = None
        self.protocol_capture_last_record_time = timestamp
        self.protocol_capture_last_source = source
        self.protocol_capture_last_changes_count = int(record.get("changes_count", 0))
        self._protocol_capture_last_signals = dict(normalized_signals)
        self._protocol_capture_last_basics = dict(normalized_basics)
        self._protocol_capture_last_status_meta = dict(normalized_status_meta)
        self._protocol_capture_last_tbox_meta = dict(normalized_tbox_meta)
        self._protocol_capture_has_snapshot = True

    async def async_add_protocol_capture_marker(self, label: str) -> None:
        """Append a human test marker without changing the telemetry baseline."""
        if not self.protocol_capture_enabled or not self.protocol_capture_path:
            raise HomeAssistantError("Режим поиска GWM-кодов выключен")
        try:
            marker = normalize_marker(label)
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err

        now = datetime.now(timezone.utc)
        sequence = self.protocol_capture_sequence + 1
        record = build_marker_record(
            sequence=sequence,
            timestamp=now,
            integration_version=VERSION,
            label=marker,
        )
        try:
            await self.hass.async_add_executor_job(
                append_jsonl,
                self.protocol_capture_path,
                record,
            )
        except Exception as err:
            self.protocol_capture_last_error = str(err)
            self.async_update_listeners()
            raise HomeAssistantError(f"Не удалось записать метку: {err}") from err

        self.protocol_capture_sequence = sequence
        self.protocol_capture_last_error = None
        self.protocol_capture_last_record_time = now
        self.protocol_capture_last_source = "marker"
        self.protocol_capture_last_changes_count = 0
        self.protocol_capture_last_marker = marker
        self.async_update_listeners()

    async def async_request_refresh_with_source(self, source: str) -> None:
        """Request a refresh and tag the next successful update with its source."""
        self._next_update_source = source
        try:
            await self.async_request_refresh()
        finally:
            if self._next_update_source == source:
                self._next_update_source = "poll"

    def _track_unknown_signals(self, unknown: dict[str, Any], now: datetime) -> None:
        timestamp = now.isoformat()
        for raw_code, value in unknown.items():
            code = str(raw_code)
            record = self.unknown_signal_history.get(code)
            if record is None:
                record = {
                    "first_seen": timestamp,
                    "last_seen": timestamp,
                    "count": 0,
                    "last_value": value,
                    "values": [],
                }
                self.unknown_signal_history[code] = record

            record["last_seen"] = timestamp
            record["last_value"] = value
            record["count"] = int(record.get("count", 0)) + 1
            values = record.setdefault("values", [])
            if value not in values:
                values.append(value)
                if len(values) > 20:
                    del values[0 : len(values) - 20]

    @property
    def capability_report(self) -> dict[str, dict[str, object]]:
        """Return capability metadata for diagnostics."""
        return capability_report(self.seen_signal_codes, self.feature_flags)

    def feature_enabled(self, capability: str) -> bool:
        """Return whether optional equipment is enabled by the user."""
        if capability in {"rear_defrost", "steering_wheel_heat"}:
            return False
        return self.feature_flags.get(capability, True)

    def command_enabled(self, command_key: str) -> bool:
        """Return whether a remote command belongs to enabled equipment."""
        capability = capability_for_command(command_key)
        return capability is None or self.feature_enabled(capability)

    @property
    def command_in_progress(self) -> bool:
        return self._command_lock.locked()

    def _ensure_remote_ready(self) -> str:
        if not self.enable_remote_controls:
            raise HomeAssistantError("Удалённое управление отключено в настройках GWM Jolion")
        if not self.security_pin:
            raise HomeAssistantError("Для удалённой команды требуется PIN безопасности GWM")
        elapsed = time.monotonic() - self._last_command_time
        if elapsed < self.command_cooldown:
            remaining = max(1, int(self.command_cooldown - elapsed))
            raise HomeAssistantError(f"Подождите ещё {remaining} сек. перед следующей командой")
        vin = (self.data or {}).get("vin")
        if not vin:
            raise HomeAssistantError("VIN автомобиля пока недоступен. Обновите данные GWM")
        return str(vin)

    async def async_send_custom_t5(
        self,
        *,
        name: str,
        instructions: dict[str, Any],
        expected_remote_type: str,
        command_key: str | None = None,
        remote_type: str = "0",
    ) -> dict[str, Any]:
        if self._command_lock.locked():
            raise HomeAssistantError("Другая удалённая команда GWM уже выполняется")

        command_started = False
        result: dict[str, Any] | None = None
        try:
            async with self._command_lock:
                if command_key == "start_engine":
                    await self.async_request_refresh_with_source("remote_start_guard")
                    reason = remote_start_block_reason((self.data or {}).get("state") or {})
                    if reason:
                        raise HomeAssistantError(
                            f"Удалённый запуск отменён: {reason}. Обновите состояние автомобиля, если оно изменилось"
                        )

                vin = self._ensure_remote_ready()
                self._last_command_time = time.monotonic()
                self.last_command_name = name
                self.last_command_status = "pending"
                self.last_command_result_code = None
                self.last_command_result_message = "Команда отправлена в GWM"
                self.last_command_at = datetime.now(timezone.utc)
                command_started = True
                self.async_update_listeners()

                try:
                    result = await self.client.async_send_t5_command(
                        vin,
                        instructions,
                        expected_remote_type,
                        security_pin=self.security_pin,
                        remote_type=remote_type,
                    )
                except Exception as err:
                    self.last_command_status = "error"
                    error_code = getattr(err, "code", None)
                    self.last_command_result_code = str(error_code) if error_code else "error"
                    self.last_command_result_message = _friendly_remote_error(err)
                    self.async_update_listeners()
                    raise

                self.last_command_status = "success"
                self.last_command_result_code = str(result.get("resultCode", ""))
                self.last_command_result_message = str(result.get("resultMsg") or "Команда выполнена")
                self.async_update_listeners()
        finally:
            if command_started:
                self.async_update_listeners()

        if result is None:
            raise HomeAssistantError("GWM не вернул результат удалённой команды")

        try:
            await self.async_request_refresh_with_source("remote_command")
        except ConfigEntryAuthFailed:
            raise
        except Exception as err:
            _LOGGER.debug("Post-command refresh failed after successful command: %s", err)
        return result

    async def async_execute_command(
        self,
        command_key: str,
        *,
        operation_time: int | None = None,
    ) -> dict[str, Any]:
        if command_key in UNSUPPORTED_COMMANDS:
            raise HomeAssistantError("Управление этим обогревом не подтверждено и отключено")
        command = COMMANDS.get(command_key)
        if command is None:
            raise HomeAssistantError(f"Unknown command: {command_key}")
        if not self.command_enabled(command_key):
            capability = capability_for_command(command_key)
            name = CAPABILITIES[capability].name if capability in CAPABILITIES else command["name"]
            raise HomeAssistantError(
                f"Функция «{name}» отключена в настройках оборудования GWM Jolion"
            )
        instructions = copy.deepcopy(command["instructions"])
        path = command.get("operation_time_path")
        if operation_time is not None and path:
            if not 1 <= int(operation_time) <= 30:
                raise HomeAssistantError("Время работы команды должно быть от 1 до 30 минут")
            _set_nested(instructions, tuple(path), str(int(operation_time)))
        return await self.async_send_custom_t5(
            name=command["name"],
            instructions=instructions,
            expected_remote_type=command["expected_remote_type"],
            command_key=command_key,
        )

    async def async_set_seat_heating(
        self, driver: int | None, passenger: int | None, operation_time: int = 5,
    ) -> dict[str, Any]:
        """Apply explicit seat settings through the guarded remote-command path."""
        for feature, value in (("seat_heat_driver", driver), ("seat_heat_passenger", passenger)):
            if value is not None and not self.feature_enabled(feature):
                raise HomeAssistantError("Подогрев этого сиденья отключён в настройках оборудования")
        try:
            instructions = build_seat_heating_instructions(driver, passenger, operation_time)
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err
        return await self.async_send_custom_t5(
            name="Подогрев сидений", instructions=instructions, expected_remote_type="0x0A",
            remote_type="" if driver == 0 and passenger == 0 else "0",
        )
