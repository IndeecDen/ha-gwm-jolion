"""Exercise actual profile/coordinator methods with storage only, no vehicle client."""
import ast
import asyncio
import copy
import importlib.util
import logging
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1] / "custom_components/gwm_jolion"
package = ModuleType("profile_test_package")
package.__path__ = [str(ROOT)]
sys.modules[package.__name__] = package
spec = importlib.util.spec_from_file_location("profile_test_package.preparation_profiles", ROOT / "preparation_profiles.py")
profiles = importlib.util.module_from_spec(spec)
spec.loader.exec_module(profiles)


@pytest.mark.parametrize("patch", [{"temperature": 33}, {"driver": 0}, {"seat_time": True}, {"climate_enabled": 1}, {"extra": 1}])
def test_profile_validation(patch):
    with pytest.raises(ValueError):
        profiles.profile_settings({**profiles.DEFAULT_SETTINGS, **patch})


def test_crud_validation_and_immutability():
    original = profiles.initial_profiles()
    result = profiles.change_profiles(original, "copy", profile_id="winter", name="Копия")
    assert len(result) == 4 and len(original) == 3
    result[-1]["settings"]["temperature"] = 24
    assert original[0]["settings"]["temperature"] == 26
    for kwargs in ({"action": "delete", "profile_id": "missing"},
                   {"action": "create", "name": " "},
                   {"action": "update", "profile_id": "winter", "name": "x" * 41}):
        with pytest.raises(ValueError): profiles.change_profiles(original, **kwargs)
    with pytest.raises(ValueError): profiles.validate_profiles(original + original)
    for i in range(17):
        original = profiles.change_profiles(original, "copy", profile_id="winter", name=str(i))
    with pytest.raises(ValueError): profiles.change_profiles(original, "copy", profile_id="winter", name="21")


def coordinator_methods():
    cls = next(n for n in ast.parse((ROOT / "coordinator.py").read_text(encoding="utf-8")).body if isinstance(n, ast.ClassDef) and n.name == "GwmJolionCoordinator")
    names = {"async_load_profiles", "async_manage_profile", "async_load_card_settings", "async_save_card_settings"}
    methods = [n for n in cls.body if isinstance(n, ast.AsyncFunctionDef) and n.name in names]
    scope = {key: getattr(profiles, key) for key in ("validate_settings", "change_profiles", "initial_profiles", "validate_profiles")}
    scope.update(HomeAssistantError=RuntimeError, _LOGGER=logging.getLogger(__name__))
    exec(compile(ast.Module(body=methods, type_ignores=[]), "profile_coordinator", "exec"), scope)
    return {name: scope[name] for name in names}


class Store:
    def __init__(self): self.data = None; self.fail = False
    async def async_load(self): return copy.deepcopy(self.data)
    async def async_save(self, value):
        if self.fail: raise OSError("disk full")
        self.data = copy.deepcopy(value)


def coordinator(store=None, settings_store=None):
    obj = SimpleNamespace(_profiles_store=store or Store(), _card_settings_store=settings_store or Store(),
        _profiles_lock=asyncio.Lock(), _card_settings_lock=asyncio.Lock(), preparation_profiles=[], card_settings={},
        climate_target_temperature=22, climate_operation_time=15, async_update_listeners=lambda: None)
    for name, method in coordinator_methods().items(): setattr(obj, name, method.__get__(obj))
    return obj


def test_storage_selection_edits_restart_and_vehicle_isolation():
    async def run():
        first, other = coordinator(), coordinator()
        await first.async_load_profiles()
        await other.async_load_profiles()
        await first.async_manage_profile("select", profile_id="winter")
        assert first.card_settings["temperature"] == 26
        assert first.card_settings["comfort_start"] is True
        await first.async_save_card_settings({"temperature": 25})
        assert first.preparation_profiles[0]["settings"]["temperature"] == 26
        await first.async_manage_profile("select", profile_id="winter")
        assert first.card_settings["temperature"] == 26
        await first.async_manage_profile("create", name="Мой", settings={**profiles.DEFAULT_SETTINGS, "temperature": 24})
        identity = first.card_settings["selected_profile"]
        await first.async_manage_profile("update", profile_id=identity, name="Новое имя", settings=profiles.DEFAULT_SETTINGS)
        assert first.preparation_profiles[-1]["name"] == "Новое имя"
        await first.async_manage_profile("copy", profile_id=identity, name="Копия")
        assert first.card_settings["selected_profile"] != identity
        await first.async_manage_profile("delete", profile_id=first.card_settings["selected_profile"])
        assert first.card_settings["selected_profile"] == ""
        second = coordinator(first._profiles_store, first._card_settings_store)
        await second.async_load_profiles()
        await second.async_load_card_settings()
        assert second.preparation_profiles == first.preparation_profiles
        assert second.card_settings == first.card_settings
        assert other.preparation_profiles == profiles.initial_profiles() and other.card_settings == {}
        for p in list(second.preparation_profiles): await second.async_manage_profile("delete", profile_id=p["id"])
        await second.async_load_profiles()
        assert second.preparation_profiles == []  # Deliberately removed templates do not reappear.
    asyncio.run(run())


def test_failed_storage_and_concurrent_creates():
    async def run():
        obj = coordinator()
        await obj.async_load_profiles()
        before = copy.deepcopy(obj.preparation_profiles)
        obj._profiles_store.fail = True
        with pytest.raises(OSError): await obj.async_manage_profile("delete", profile_id="winter")
        assert obj.preparation_profiles == before
        obj._profiles_store.fail = False
        await asyncio.gather(*(obj.async_manage_profile("create", name=str(i), settings=profiles.DEFAULT_SETTINGS) for i in range(3)))
        assert len(obj.preparation_profiles) == 6
        with pytest.raises(RuntimeError): await obj.async_manage_profile("select", profile_id="missing")
    asyncio.run(run())
