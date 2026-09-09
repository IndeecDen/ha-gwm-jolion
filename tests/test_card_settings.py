import ast
import asyncio
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import pytest

ROOT = Path(__file__).resolve().parents[1] / "custom_components/gwm_jolion"
spec = importlib.util.spec_from_file_location("card_settings_test", ROOT / "card_settings.py")
settings = importlib.util.module_from_spec(spec)
spec.loader.exec_module(settings)

@pytest.mark.parametrize("patch", [{"driver":0}, {"temperature":99}, {"seat_time":True}, {"comfort_start":1}, {"vin":"x"}])
def test_invalid_preferences(patch):
    with pytest.raises(ValueError): settings.validate_settings(patch)


def test_store_restart_and_merge_without_remote_calls():
    cls = next(n for n in ast.parse((ROOT / "coordinator.py").read_text(encoding="utf-8")).body if isinstance(n, ast.ClassDef) and n.name == "GwmJolionCoordinator")
    methods = [n for n in cls.body if isinstance(n, ast.AsyncFunctionDef) and n.name in ("async_load_card_settings", "async_save_card_settings")]
    scope = dict(validate_settings=settings.validate_settings, HomeAssistantError=RuntimeError)
    exec(compile(ast.Module(body=methods,type_ignores=[]), "settings", "exec"),scope)
    class Store:
        data = None
        async def async_save(self, value): self.data = dict(value)
        async def async_load(self): return self.data
    store=Store()
    def coordinator():
        return SimpleNamespace(_card_settings_store=store,card_settings={},_card_settings_lock=asyncio.Lock(),climate_target_temperature=22,climate_operation_time=15,async_update_listeners=lambda:None)
    async def run():
        first=coordinator()
        await scope['async_save_card_settings'](first, {'temperature':26,'driver':2,'driver_enabled':False})
        await scope['async_save_card_settings'](first, {'seat_time':9})
        second=coordinator()
        await scope['async_load_card_settings'](second)
        assert second.card_settings == {'temperature':26,'driver':2,'driver_enabled':False,'seat_time':9}
        assert second.climate_target_temperature == 26
    asyncio.run(run())
