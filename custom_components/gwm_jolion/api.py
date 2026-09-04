"""Async client for the unofficial Russian GWM cloud."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import socket
import time
import uuid
from typing import Any
from urllib.parse import parse_qs, quote_plus, urlencode, urlparse

from aiohttp import ClientError, ClientSession
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError

from .const import (
    APP_ID,
    APP_KEY,
    APP_SEC,
    APP_VERSION,
    AUTH_PREFIX,
    BASE_URL,
    BRAND,
    COUNTRY,
    ENDPOINT_CHECK_SECURITY_PASSWORD,
    ENDPOINT_FIND_STATUS,
    ENDPOINT_LAST_STATUS,
    ENDPOINT_LOGIN,
    ENDPOINT_MODIFY_REMOTE_CTL_INFO,
    ENDPOINT_T5_CTRL_RESULT,
    ENDPOINT_T5_SEND_CMD,
    ENDPOINT_VEHICLE_BASICS_INFO,
    ENDPOINT_VEHICLES,
    ENTERPRISE_ID,
    LANGUAGE,
    REGION_CODE,
    SYSTEM_TYPE,
    TERMINAL,
)
from .helpers import build_state, normalize_phone, redact_vehicle, vehicle_basics_snapshot
from .vehicle_data import calculate_fuel_percent, describe_structure, normalize_vehicle_metadata

_LOGGER = logging.getLogger(__name__)


class GwmJolionApiError(HomeAssistantError):
    """Raised when the GWM cloud returns an error."""

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.code = code


class GwmJolionApiClient:
    """Small async client for the Russian GWM API."""

    def __init__(
        self,
        session: ClientSession,
        phone: str,
        password: str,
        device_id: str,
        country: str,
        country_code: str,
    ) -> None:
        self._session = session
        self._phone = normalize_phone(phone)
        self._password = password
        self._device_id = device_id
        self._country = country
        self._country_code = country_code
        self._access_token: str | None = None
        self._login_lock = asyncio.Lock()

    async def async_login(self) -> None:
        async with self._login_lock:
            body = {
                "account": self._phone,
                "password": self._password,
                "agreement": [1, 2, 18, 19],
                "smsCode": None,
                "msgType": None,
                "model": "Home Assistant",
                "type": 1,
                "deviceId": self._device_id,
                "appType": 0,
                "pushToken": "",
                "country": self._country,
                "countryCode": self._country_code,
                "isEncrypt": False,
            }
            payload = await self._request("POST", ENDPOINT_LOGIN, body=body, with_token=False)
            data = payload.get("data") or {}
            token = data.get("accessToken")
            if not token:
                raise ConfigEntryAuthFailed("GWM login did not return accessToken")
            self._access_token = str(token)

    async def async_update(self) -> dict[str, Any]:
        await self._ensure_login()
        vehicles = await self._get_vehicles()
        if not vehicles:
            raise GwmJolionApiError("No vehicles returned by GWM account")

        # Alpha currently exposes the first vehicle from the account. Multi-vehicle
        # selection will be added without changing the protocol client itself.
        car = vehicles[0]
        vin = car.get("vin")
        imsi = car.get("imsi")
        vehicle_id = car.get("vehicleId")
        if not vin:
            raise GwmJolionApiError("Vehicle does not contain VIN")
        vin = str(vin)

        status = await self._get_last_status(vin)
        tbox: dict[str, Any] = {}
        if imsi and vehicle_id:
            try:
                tbox = await self._find_status(str(imsi), str(vehicle_id), vin)
            except GwmJolionApiError as err:
                _LOGGER.debug("findStatus unavailable: %s", err)

        basics: dict[str, Any] = {}
        basics_diagnostics: dict[str, Any] = {
            "status": "not_requested",
            "response_code": None,
            "description": None,
            "response_structure": None,
        }
        try:
            basics_payload = await self._get_vehicle_basics_payload(vin)
            raw_data = basics_payload.get("data")
            basics = raw_data if isinstance(raw_data, dict) else {}
            has_data = raw_data not in (None, {}, [])
            basics_diagnostics = {
                "status": "success_with_data" if has_data else "success_empty",
                "response_code": str(basics_payload.get("code") or ""),
                "description": basics_payload.get("description") or basics_payload.get("message"),
                "data_type": type(raw_data).__name__,
                "response_structure": describe_structure(basics_payload),
            }
        except GwmJolionApiError as err:
            text = str(err)
            lowered = text.lower()
            unsupported_markers = ("unsupported", "not support", "not supported", "не поддерж")
            basics_diagnostics = {
                "status": "unsupported" if any(marker in lowered for marker in unsupported_markers) else "error",
                "response_code": err.code,
                "description": text,
                "response_structure": None,
            }
            _LOGGER.debug("vehicleBasicsInfo unavailable: %s", err)

        state = build_state(status, tbox, basics)
        location = {
            "latitude": status.get("latitude"),
            "longitude": status.get("longitude"),
            "gps_accuracy": 50,
        }
        vehicle_name = car.get("vehicleName") or car.get("modelName") or "Haval Jolion"
        car_data = redact_vehicle(car)
        normalized = normalize_vehicle_metadata(car_data)
        state.update(normalized)
        fuel_percent = calculate_fuel_percent(state.get("fuel_liters"), state.get("tank_capacity_l"))
        if fuel_percent is not None:
            state["fuel_percent"] = fuel_percent

        return {
            "vin": vin,
            "vehicle": car_data,
            "vehicle_name": vehicle_name,
            "state": state,
            "location": location,
            "vehicle_basics": vehicle_basics_snapshot(basics),
            "vehicle_basics_diagnostics": basics_diagnostics,
        }

    async def async_check_security_password(self, security_pin: str, check_type: int = 3) -> str:
        await self._ensure_login()
        pin_md5 = hashlib.md5(security_pin.encode("utf-8")).hexdigest()
        await self._request(
            "POST",
            ENDPOINT_CHECK_SECURITY_PASSWORD,
            body={"type": str(check_type), "securityPassword": pin_md5},
        )
        return pin_md5

    async def async_update_climate_defaults(self, vin: str, temperature: int, operation_time_minutes: int) -> None:
        await self._ensure_login()
        body = {
            "airConditionerTemperature": str(temperature),
            "airConditionerTime": str(operation_time_minutes * 60),
            "vin": vin,
        }
        await self._request("POST", ENDPOINT_MODIFY_REMOTE_CTL_INFO, body=body, vin_header=vin)

    async def async_send_t5_command(
        self,
        vin: str,
        instructions: dict[str, Any],
        expected_remote_type: str,
        security_pin: str | None = None,
    ) -> dict[str, Any]:
        await self._ensure_login()
        security_password = None
        if security_pin:
            security_password = await self.async_check_security_password(security_pin, 3)
        seq_no = _make_t5_seq_no()
        body = {
            "vin": vin,
            "seqNo": seq_no,
            "remoteType": "0",
            "instructions": instructions,
            "securityPassword": security_password,
            "type": 3,
            "compoundCommandTemplateId": None,
        }
        _LOGGER.debug(
            "Sending T5 command: seqNo=%s expectedRemoteType=%s instructionKeys=%s type=3 hasSecurityPassword=%s",
            seq_no,
            expected_remote_type,
            list(instructions.keys()),
            bool(security_password),
        )
        send_payload = await self._request("POST", ENDPOINT_T5_SEND_CMD, body=body, vin_header=vin)
        data = send_payload.get("data") or {}
        if isinstance(data, dict):
            seq_no = str(data.get("seqNo") or seq_no)
        await asyncio.sleep(2)
        return await self.async_poll_t5_result(vin, seq_no, expected_remote_type)

    async def async_poll_t5_result(
        self,
        vin: str,
        seq_no: str,
        expected_remote_type: str,
        timeout: int = 300,
        interval: int = 1,
    ) -> dict[str, Any]:
        success_codes = {"0", "6", "10"}
        pending_codes = {"1000", "2000"}
        deadline = time.time() + timeout
        last_error_code: str | None = None
        last_error_msg: str | None = None
        while time.time() < deadline:
            await asyncio.sleep(interval)
            try:
                payload = await self._request(
                    "GET",
                    ENDPOINT_T5_CTRL_RESULT,
                    params={"seqNo": seq_no},
                    vin_header=vin,
                )
            except GwmJolionApiError:
                continue
            data = payload.get("data")
            if not isinstance(data, list):
                continue
            matched = [item for item in data if str(item.get("remoteType") or "") == expected_remote_type]
            if not matched:
                continue
            for item in matched:
                result_code = str(item.get("resultCode", ""))
                if result_code in success_codes:
                    _LOGGER.debug(
                        "T5 command succeeded: remoteType=%s code=%s msg=%s",
                        expected_remote_type,
                        result_code,
                        item.get("resultMsg") or "",
                    )
                    return item
            if any(str(item.get("resultCode", "")) in pending_codes for item in matched):
                continue
            for item in matched:
                last_error_code = str(item.get("resultCode", ""))
                last_error_msg = str(item.get("resultMsg") or "")
            _LOGGER.debug(
                "T5 non-final result: remoteType=%s code=%s msg=%s",
                expected_remote_type,
                last_error_code,
                last_error_msg,
            )
        if last_error_code:
            raise HomeAssistantError(
                f"Command failed: {last_error_msg}" if last_error_msg else f"Error code {last_error_code}"
            )
        raise HomeAssistantError("Command timed out after 300 seconds")

    async def _ensure_login(self) -> None:
        if not self._access_token:
            await self.async_login()

    async def _get_vehicles(self) -> list[dict[str, Any]]:
        payload = await self._request("GET", ENDPOINT_VEHICLES)
        data = payload.get("data") or []
        return data if isinstance(data, list) else []

    async def _get_last_status(self, vin: str) -> dict[str, Any]:
        payload = await self._request(
            "GET",
            ENDPOINT_LAST_STATUS,
            params={"vin": vin, "seqNo": "", "modelId": ""},
            vin_header=vin,
        )
        data = payload.get("data") or {}
        return data if isinstance(data, dict) else {}

    async def _find_status(self, imsi: str, vehicle_id: str, vin: str) -> dict[str, Any]:
        payload = await self._request(
            "GET",
            ENDPOINT_FIND_STATUS,
            params={"imsi": imsi, "vehicleId": vehicle_id},
            vin_header=vin,
        )
        data = payload.get("data") or {}
        return data if isinstance(data, dict) else {}

    async def _get_vehicle_basics_payload(self, vin: str) -> dict[str, Any]:
        return await self._request(
            "GET",
            ENDPOINT_VEHICLE_BASICS_INFO,
            params={"vin": vin, "flag": "true"},
            vin_header=vin,
        )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        body: dict[str, Any] | None = None,
        with_token: bool = True,
        vin_header: str | None = None,
        retry_auth: bool = True,
    ) -> dict[str, Any]:
        params = params or {}
        body_json = json.dumps(body, ensure_ascii=False, separators=(",", ":")) if body is not None else ""
        query = urlencode(params, doseq=False)
        url = BASE_URL + path + ("?" + query if query else "")
        headers = self._headers(method, path, url, body_json, with_token, vin_header)
        try:
            async with self._session.request(
                method,
                url,
                headers=headers,
                data=body_json.encode("utf-8") if body is not None else None,
                timeout=30,
            ) as response:
                text = await response.text()
        except ClientError as err:
            raise GwmJolionApiError(f"Cannot connect to GWM RU: {err}") from err
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as err:
            raise GwmJolionApiError(f"Invalid GWM response: {text[:200]}") from err
        code = str(payload.get("code"))
        if code == "000000":
            return payload
        if with_token and retry_auth and code in {"401", "401000", "308001", "308002", "308003"}:
            self._access_token = None
            await self.async_login()
            return await self._request(
                method,
                path,
                params=params,
                body=body,
                with_token=with_token,
                vin_header=vin_header,
                retry_auth=False,
            )
        description = str(payload.get("description") or payload.get("message") or code)
        _LOGGER.debug("GWM error: code=%s description=%s path=%s", code, description, path)
        if not with_token:
            raise ConfigEntryAuthFailed(description)
        raise GwmJolionApiError(description, code=code)

    def _headers(
        self,
        method: str,
        path: str,
        url: str,
        body_json: str,
        with_token: bool,
        vin: str | None,
    ) -> dict[str, str]:
        timestamp, nonce, signature = sign_request(method, path, url, body_json)
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json; charset=UTF-8",
            f"{AUTH_PREFIX}-auth-appkey": APP_KEY,
            f"{AUTH_PREFIX}-auth-timestamp": timestamp,
            f"{AUTH_PREFIX}-auth-sign": signature,
            f"{AUTH_PREFIX}-auth-nonce": nonce,
            "ip": local_ip(),
            "rs": "2",
            "appId": APP_ID,
            "brand": BRAND,
            "terminal": TERMINAL,
            "enterpriseId": ENTERPRISE_ID,
            "systemType": SYSTEM_TYPE,
            "cVer": APP_VERSION,
            "timeZone": "GMT+03:00",
            "channel": "APP",
            "language": LANGUAGE,
            "regionCode": REGION_CODE,
            "country": COUNTRY,
            "communityBrand": "1",
            "deviceId": self._device_id,
            "iccid": self._device_id,
            "User-Agent": "GWM",
        }
        if with_token and self._access_token:
            headers["accessToken"] = self._access_token
        if vin:
            headers["vin"] = vin
        return headers


def sign_request(method: str, path: str, full_url: str, body_json: str = "") -> tuple[str, str, str]:
    timestamp = str(int(time.time() * 1000))
    nonce = hashlib.md5(str(time.time_ns()).encode("utf-8")).hexdigest()[:16]
    auth_string = (
        f"{AUTH_PREFIX}-auth-appkey:{APP_KEY}"
        f"{AUTH_PREFIX}-auth-nonce:{nonce}"
        f"{AUTH_PREFIX}-auth-timestamp:{timestamp}"
    )
    if method.upper() == "GET":
        parameters = format_get_parameter(full_url)
    elif method.upper() == "POST":
        parameters = "json=" + body_json
    else:
        parameters = ""
    raw = method.upper() + path + auth_string + parameters + APP_SEC
    raw = re.sub(r"\s*|\t|\r|\n", "", raw)
    encoded = quote_plus(raw, safe="")
    return timestamp, nonce, hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def format_get_parameter(full_url: str) -> str:
    query = parse_qs(urlparse(full_url).query, keep_blank_values=True)
    output = ""
    for key in sorted(set(query.keys())):
        value = query[key][0] if query[key] else ""
        output += key.lower() + "=" + value
    return output


def local_ip() -> str:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
        sock.close()
        return ip
    except OSError:
        return "127.0.0.1"


def _make_t5_seq_no() -> str:
    return uuid.uuid4().hex + "1234"
