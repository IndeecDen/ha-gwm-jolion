"""The Disk access probe must also run on its own after startup and log its verdict.

A user only sees the button attributes if they press it, so the integration probes
once after setup and reports failures in the log with a plain-language hint.
"""
import ast
import asyncio
import logging
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1] / "custom_components/gwm_jolion"
LOGGER = logging.getLogger("gwm_jolion.locator")


def locator_tree():
    return ast.parse((ROOT / "locator.py").read_text(encoding="utf-8"))


def check_method():
    """Load LocatorUpload.check_disk_access without importing Home Assistant."""
    cls = next(n for n in locator_tree().body
               if isinstance(n, ast.ClassDef) and n.name == "HybridHistory")
    node = next(n for n in cls.body
                if isinstance(n, ast.AsyncFunctionDef) and n.name == "check_disk_access")
    scope = {"asyncio": asyncio, "_LOGGER": LOGGER,
             "notify_access": lambda hass, result: hass.notified.append(result)}
    exec(compile(ast.Module(body=[node], type_ignores=[]), "locator.py", "exec"), scope)
    return scope["check_disk_access"]


def run(result=None, error=None):
    calls = []
    notified = []

    async def check_access():
        calls.append(True)
        if error is not None:
            raise error
        return result

    history = SimpleNamespace(relay=SimpleNamespace(check_access=check_access),
                              hass=SimpleNamespace(notified=notified))
    method = check_method()
    return lambda: method(history), calls, notified


def test_successful_startup_probe_is_logged_and_returned(caplog):
    result = {"status": "ok", "summary": "Все проверки пройдены.", "hint": ""}
    method, calls, notified = run(result)
    with caplog.at_level(logging.INFO, logger="gwm_jolion.locator"):
        outcome = asyncio.run(method())
    assert outcome == result and calls == [True]
    assert "Яндекс.Диск доступен" in caplog.text
    # A healthy Disk stays silent: no notification for a passing check.
    assert notified == []


def test_failed_startup_probe_logs_summary_and_hint_without_secrets(caplog):
    result = {"status": "auth_error", "token": "unauthorized",
              "summary": "Диск отклонил доступ: токен — токен отклонён.",
              "hint": "Токен недействителен или отозван."}
    method, _, notified = run(result)
    with caplog.at_level(logging.WARNING, logger="gwm_jolion.locator"):
        outcome = asyncio.run(method())
    assert outcome == result
    assert "Диск отклонил доступ" in caplog.text and "Подсказка: Токен" in caplog.text
    assert "OAuth" not in caplog.text and "unauthorized" not in caplog.text
    # A broken Disk must reach the user without them hunting through attributes.
    assert notified == [result]


def test_failing_probe_never_breaks_setup(caplog):
    method, _, notified = run(error=RuntimeError("synthetic oauth crash"))
    with caplog.at_level(logging.ERROR, logger="gwm_jolion.locator"):
        assert asyncio.run(method()) is None
    assert "Проверка доступа к Яндекс.Диску завершилась сбоем" in caplog.text
    assert notified == []


def test_probe_is_skipped_without_a_yandex_relay():
    method = check_method()
    assert asyncio.run(method(SimpleNamespace(relay=None))) is None
    assert asyncio.run(method(SimpleNamespace(relay=SimpleNamespace()))) is None
    assert asyncio.run(method(SimpleNamespace())) is None


def test_setup_starts_the_probe_in_the_background():
    """initialize() must schedule the probe instead of waiting for a button press."""
    source = (ROOT / "locator.py").read_text(encoding="utf-8")
    cls = next(n for n in locator_tree().body
               if isinstance(n, ast.ClassDef) and n.name == "HybridHistory")
    init = next(n for n in cls.body
                if isinstance(n, ast.AsyncFunctionDef) and n.name == "initialize")
    body = ast.get_source_segment(source, init) or ""
    assert "async_create_background_task(self.check_disk_access()" in body
