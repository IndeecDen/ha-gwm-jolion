"""Exercise the real options method offline, without importing Home Assistant."""
import ast
import asyncio
import __future__
import hashlib
from pathlib import Path
import re
import sys
from types import ModuleType, SimpleNamespace
from urllib.parse import urlsplit

import pytest
import voluptuous as vol

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "gwm_jolion"


def literal_constants(filename):
    result = {}
    for node in ast.parse((ROOT / filename).read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign):
            try:
                value = ast.literal_eval(node.value)
            except (ValueError, TypeError):
                continue
            for target in node.targets:
                if isinstance(target, ast.Name):
                    result[target.id] = value
    return result


@pytest.fixture
def options_flow(monkeypatch):
    tree = ast.parse((ROOT / "config_flow.py").read_text(encoding="utf-8"))
    scope = {"__package__": "secret_form_test", "re": re, "hashlib": hashlib,
             "vol": vol, **literal_constants("const.py"),
             **literal_constants("protocol_capture.py"),
             **literal_constants("config_flow.py")}
    locator = literal_constants("locator.py")
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "locator":
            scope.update({alias.asname or alias.name: locator[alias.name] for alias in node.names})
    # Only the HA UI boundary is replaced. Validation and flow logic are real.
    scope.update(selector=SimpleNamespace(
        TextSelector=lambda config: str, TextSelectorConfig=lambda **kw: kw,
        TextSelectorType=SimpleNamespace(PASSWORD="password")),
        GPS_INTERVAL_SELECTOR=int, POLL_INTERVAL_SELECTOR=int,
        MANUAL_CAPABILITY_OPTIONS={}, resolve_manual_capabilities=lambda options: {})
    validators = ModuleType("secret_form_test.locator_yandex")
    validators.__dict__.update(re=re, urlsplit=urlsplit)
    nodes = [n for n in ast.parse((ROOT / "locator_yandex.py").read_text(encoding="utf-8")).body
             if isinstance(n, ast.FunctionDef) and n.name in
             {"valid_disk_token", "valid_folder", "valid_public_url"}]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "locator_yandex.py", "exec",
                 flags=__future__.annotations.compiler_flag), validators.__dict__)
    monkeypatch.setitem(sys.modules, validators.__name__, validators)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "GwmJolionOptionsFlow")
    method = next(n for n in cls.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "async_step_init")
    exec(compile(ast.Module(body=[method], type_ignores=[]), "config_flow.py", "exec",
                 flags=__future__.annotations.compiler_flag), scope)
    saved = {scope["TOKEN"]: "saved-oauth-token", scope["LOCATOR_KEY"]: "K" * 32,
             scope["LOCATOR_HASH"]: hashlib.sha256(b"K" * 32).hexdigest(),
             scope["CONF_SECURITY_PIN"]: "1234", "custom_preference": 42}
    flow = SimpleNamespace(
        config_entry=SimpleNamespace(entry_id="car", options=saved, data={"password": "account-secret"}),
        hass=SimpleNamespace(config_entries=SimpleNamespace(async_entries=lambda domain: [])),
        async_create_entry=lambda **kw: dict(type="create", **kw),
        async_show_form=lambda **kw: dict(type="form", **kw))
    return scope, flow, lambda value=None: asyncio.run(scope["async_step_init"](flow, value))


@pytest.mark.parametrize("redisplay", [False, True])
def test_secret_controls_never_return_saved_or_submitted_defaults(options_flow, redisplay):
    scope, flow, submit = options_flow
    keys = [scope[name] for name in ("TOKEN", "LOCATOR_KEY", "CONF_SECURITY_PIN")]
    payload = {key: "new-private-value" for key in keys} if redisplay else None
    result = submit(payload)
    assert result["type"] == "form"
    defaults = {marker.schema: marker.default() if callable(marker.default) else marker.default
                for marker in result["data_schema"].schema}
    for key in keys:
        assert defaults[key] in (vol.UNDEFINED, "")
    assert "account-secret" not in repr(defaults)
    assert flow.config_entry.options[scope["TOKEN"]] == "saved-oauth-token"


@pytest.mark.parametrize("blank", [None, "", "   "])
def test_empty_secret_controls_preserve_saved_credentials(options_flow, blank):
    scope, flow, submit = options_flow
    names = ("TOKEN", "LOCATOR_KEY", "CONF_SECURITY_PIN", "LOCATOR_HASH")
    before = dict(flow.config_entry.options)
    payload = {} if blank is None else {scope[name]: blank for name in names[:3]}
    result = submit(payload)
    assert result["type"] == "create"
    for name in names:
        assert result["data"][scope[name]] == before[scope[name]]
    assert result["data"]["custom_preference"] == 42
    assert flow.config_entry.options == before


def test_failed_submission_reports_saved_pin_presence(options_flow):
    scope, flow, submit = options_flow
    result = submit({scope["CONF_SECURITY_PIN"]: "", scope["LOCATOR_KEY"]: "too-short"})
    assert result["type"] == "form"
    assert result["description_placeholders"]["pin_status"] == "сохранён"


@pytest.mark.parametrize("clear", [False, True])
def test_replacements_and_explicit_pin_deletion(options_flow, clear):
    scope, flow, submit = options_flow
    result = submit({scope["TOKEN"]: "replacement-oauth-token",
                     scope["LOCATOR_KEY"]: "R" * 32,
                     scope["CONF_SECURITY_PIN"]: "9876",
                     scope["CLEAR_SECURITY_PIN"]: clear})
    assert result["type"] == "create"
    saved = result["data"]
    assert saved[scope["TOKEN"]] == "replacement-oauth-token"
    assert saved[scope["LOCATOR_KEY"]] == "R" * 32
    assert saved[scope["LOCATOR_HASH"]] == hashlib.sha256(b"R" * 32).hexdigest()
    if clear:
        assert scope["CONF_SECURITY_PIN"] not in saved
    else:
        assert saved[scope["CONF_SECURITY_PIN"]] == "9876"
    assert saved["custom_preference"] == 42
    assert flow.config_entry.data == {"password": "account-secret"}


def test_blank_controls_roundtrip_with_disk_cleanup(options_flow):
    scope, flow, submit = options_flow
    flow.config_entry.options.update({
        scope["LOCATOR_ENABLED"]: True, scope["CLEANUP"]: True,
        "golion_locator_transport": "yandex_disk",
        "golion_locator_yandex_public_url": "https://disk.yandex.ru/d/example"})
    form = submit()
    payload = form["data_schema"]({scope[name]: "" for name in
                                    ("TOKEN", "LOCATOR_KEY", "CONF_SECURITY_PIN")})
    result = submit(payload)
    assert result["type"] == "create"
    for name in ("TOKEN", "LOCATOR_KEY", "LOCATOR_HASH", "CONF_SECURITY_PIN", "CLEANUP"):
        assert result["data"][scope[name]] == flow.config_entry.options[scope[name]]
