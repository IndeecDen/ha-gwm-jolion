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
from .capabilities import capability_report
from .command_safety import remote_start_block_reason
from .commands import COMMANDS
from .const import DEFAULT_CLIMATE_RUNTIME, DEFAULT_CLIMATE_TEMPERATURE, DOMAIN
from .protocol import SIGNALS, VerificationStatus

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
    """Coordinate polling, diagnostics and serialized remote commands."""

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
    ) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=timedelta(seconds=poll_interval))
        self.client = client
        self.entry_id = entry_id
        self.enable_remote_controls = enable_remote_controls
        self.command_cooldown = command_cooldown
        self.security_pin = security_pin
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
        self.seen_signal_codes: set[str] = set()

    async def _async_update_data(self) -> dict[str, Any]:
        data = await self.client.async_update()
        now = datetime.now(timezone.utc)
        state = data.get("state") or {}
        seen = state.get("_seen_signals") or {}
        raw_unknown = state.get("_unknown_signals") or {}
        unknown_for_history: dict[str, Any] = (
            dict(raw_unknown) if isinstance(raw_unknown, dict) else {}
        )

        if isinstance(seen, dict):
            self.seen_signal_codes.update(str(code) for code in seen)
            for raw_code, value in seen.items():
                code = str(raw_code)
                info = SIGNALS.get(code)
                if info is not None and info.status == VerificationStatus.UNKNOWN:
                    unknown_for_history.setdefault(code, value)

        if unknown_for_history:
            self._track_unknown_signals(unknown_for_history, now)

        self.last_successful_update = now
        return data

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
        """Return informational capability metadata for diagnostics."""
        return capability_report(self.seen_signal_codes)

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
    ) -> dict[str, Any]:
        if self._command_lock.locked():
            raise HomeAssistantError("Другая удалённая команда GWM уже выполняется")

        async with self._command_lock:
            if command_key == "start_engine":
                # Use fresh cloud telemetry for the conservative start guard.
                await self.async_request_refresh()
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
            self.async_update_listeners()
            try:
                result = await self.client.async_send_t5_command(
                    vin,
                    instructions,
                    expected_remote_type,
                    security_pin=self.security_pin,
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
            try:
                await self.async_request_refresh()
            except ConfigEntryAuthFailed:
                raise
            except Exception as err:
                _LOGGER.debug("Post-command refresh failed after successful command: %s", err)
            return result

    async def async_execute_command(self, command_key: str, *, operation_time: int | None = None) -> dict[str, Any]:
        command = COMMANDS.get(command_key)
        if command is None:
            raise HomeAssistantError(f"Unknown command: {command_key}")
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
