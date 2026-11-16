"""Disk access probe results reach diagnostics without exposing secrets.

The probe runs behind the diagnostic button; the downloaded diagnostics must show
the same cached verdict so a user can attach one file when asking for support.
"""
import ast
import json
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1] / "custom_components/gwm_jolion"


def diagnostics_scope():
    """Load diagnostics.py without Home Assistant, keeping its real helpers."""
    tree = ast.parse((ROOT / "diagnostics.py").read_text(encoding="utf-8"))
    body = [node for node in tree.body
            if not isinstance(node, (ast.Import, ast.ImportFrom))]
    scope = {
        "Path": Path,
        "Any": object,
        "DOMAIN": "gwm_jolion",
        "VERSION": "0.0-test",
        "ConfigEntry": object,
        "DeviceEntry": object,
        "HomeAssistant": object,
        "GwmJolionCoordinator": object,
        "snapshot": lambda coordinator: {"stub": True},
        "signal_report": lambda codes: {"count": len(codes)},
        "read_jsonl_for_diagnostics": lambda path: {},
    }
    exec(compile(ast.Module(body=body, type_ignores=[]), "diagnostics.py", "exec"), scope)
    return scope


def fake_relay(**overrides):
    """Mirror the relay surface diagnostics reads; write token stays synthetic."""
    base = dict(status="waiting", token="synthetic-write-token", offset=3,
                cleanup_enabled=True, cleanup_blocked=False, cleanup_error=None,
                cleanup_deleted=1, grace_seconds=86400, throttle_until=0.0,
                last_diagnostics=None)
    base.update(overrides)
    return SimpleNamespace(**base)


def fake_coordinator(relay):
    return SimpleNamespace(
        data={"state": {"battery": 80}, "vehicle": {"model": "Jolion"}},
        last_successful_update=None,
        last_command_at=None,
        protocol_capture_path=None,
        protocol_capture_last_record_time=None,
        trip_history=SimpleNamespace(relay=relay),
        update_health={},
        gps_update_health={},
        seen_signal_codes=set(),
        unknown_signal_history=[],
        signal_change_history=[],
        capability_report={},
        protocol_capture_enabled=False,
        protocol_capture_sequence=0,
        protocol_capture_last_source=None,
        protocol_capture_last_changes_count=0,
        protocol_capture_last_marker=None,
        protocol_capture_last_error=None,
        last_command_name=None,
        last_command_result_code=None,
        last_command_result_message=None,
        command_in_progress=False,
    )


def payload_for(relay):
    scope = diagnostics_scope()
    entry = SimpleNamespace(data={"phone": "+79990001122", "password": "synthetic-pass-9"},
                            options={})
    return scope, scope["_redact"](
        scope["_base_diagnostics_payload"](entry, fake_coordinator(relay)))


def test_access_check_is_reported_with_readable_status_names():
    probe = {"status": "ok", "token": "ok", "folder": "ok",
             "public_folder": "ok", "write_access": "not_checked"}
    relay = fake_relay(last_diagnostics=dict(probe))
    _, payload = payload_for(relay)
    assert payload["locator_relay"]["access_check"] == {
        "status": "ok",
        "token_access": "ok",
        "folder_access": "ok",
        "public_folder_access": "ok",
        "write_access": "not_checked",
    }
    # The payload owns its copy: a downstream edit must not corrupt the cache.
    payload["locator_relay"]["access_check"]["status"] = "tampered"
    assert relay.last_diagnostics["status"] == "ok"


def test_access_check_is_none_before_the_first_probe():
    assert payload_for(fake_relay())[1]["locator_relay"]["access_check"] is None
    assert payload_for(fake_relay(last_diagnostics="corrupt"))[1]["locator_relay"]["access_check"] is None


def test_probe_verdict_does_not_leak_or_double_redact_credentials():
    probe = {"status": "auth_error", "token": "unauthorized", "folder": "ok",
             "public_folder": "ok", "write_access": "not_checked"}
    _, payload = payload_for(fake_relay(last_diagnostics=dict(probe)))
    rendered = json.dumps(payload)
    assert "synthetic-pass-9" not in rendered and "+79990001122" not in rendered
    assert "synthetic-write-token" not in rendered
    assert payload["config"]["data"]["password"] == "**REDACTED**"
    # "token" is a redacted key name, so the verdict must live under a new name.
    assert payload["locator_relay"]["access_check"]["token_access"] == "unauthorized"
    assert payload["locator_relay"]["has_write_token"] is True
    assert payload["privacy"]["credentials_included"] is False
