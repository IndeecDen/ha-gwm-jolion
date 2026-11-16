"""Exercise the Disk diagnostic button without HA or network access."""
import ast
import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

ROOT = Path(__file__).resolve().parents[1] / "custom_components/gwm_jolion"


def button_class():
    class Entity:
        def __init__(self, coordinator): self.coordinator = coordinator
        def async_write_ha_state(self): self.written = True
    class Button: pass
    tree = ast.parse((ROOT / 'button.py').read_text(encoding='utf-8'))
    node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'GwmJolionCheckDiskButton')
    scope = {'GwmJolionEntity': Entity, 'ButtonEntity': Button,
             'EntityCategory': SimpleNamespace(DIAGNOSTIC='diagnostic')}
    exec(compile(ast.Module(body=[node], type_ignores=[]), 'button.py', 'exec'), scope)
    return scope[node.name]


def test_disk_button_checks_only_disk_and_exposes_cached_result():
    relay = SimpleNamespace(closed=False, last_diagnostics=None)
    async def check():
        relay.last_diagnostics = {'status': 'ok', 'token': 'ok', 'folder': 'ok'}
        return relay.last_diagnostics.copy()
    relay.check_access = AsyncMock(side_effect=check)
    coordinator = SimpleNamespace(entry_id='test', trip_history=SimpleNamespace(relay=relay))
    button = button_class()(coordinator)
    assert button.available
    assert button.extra_state_attributes == {'access_check': None}
    asyncio.run(button.async_press())
    relay.check_access.assert_awaited_once_with()
    assert button.written
    assert button.extra_state_attributes['access_check']['status'] == 'ok'
    exposed = button.extra_state_attributes['access_check']
    exposed['status'] = 'tampered'
    assert relay.last_diagnostics['status'] == 'ok'


def test_disk_button_unavailable_without_relay():
    button = button_class()(SimpleNamespace(entry_id='test', trip_history=SimpleNamespace(relay=None)))
    assert not button.available
    assert button.extra_state_attributes == {'access_check': None}
    asyncio.run(button.async_press())
