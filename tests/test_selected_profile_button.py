"""Exercise the button's real methods and coordinator profile-to-command mapping."""
import ast
import asyncio
from types import SimpleNamespace

import pytest

from test_preparation_profiles import ROOT, profiles


def start_method():
    cls = next(n for n in ast.parse((ROOT / "coordinator.py").read_text(encoding="utf-8")).body
               if isinstance(n, ast.ClassDef) and n.name == "GwmJolionCoordinator")
    method = next(n for n in cls.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "async_start_selected_profile")
    scope = {"HomeAssistantError": RuntimeError, "profile_settings": profiles.profile_settings}
    exec(compile(ast.Module(body=[method], type_ignores=[]), "selected_profile", "exec"), scope)
    return scope[method.name]


def test_uses_current_draft_and_omits_absent_equipment():
    async def run():
        calls=[]
        async def launch(**kwargs): calls.append(kwargs)
        first=SimpleNamespace(preparation_profiles=profiles.initial_profiles(),
            card_settings={"selected_profile":"winter", "temperature":24, "driver_enabled":False},
            feature_enabled=lambda feature: feature == "seat_heat_driver", async_start_with_comfort=launch)
        await start_method()(first)
        assert calls == [dict(temperature=24,climate_time=15,engine_time=15,climate_enabled=True,driver=0,passenger=None,seat_time=10)]
        # Same profile ID belongs to another vehicle and uses that vehicle's draft.
        second=SimpleNamespace(preparation_profiles=profiles.initial_profiles(),
            card_settings={"selected_profile":"summer", "climate_enabled":False},
            feature_enabled=lambda feature: True, async_start_with_comfort=launch)
        await start_method()(second)
        assert calls[-1]["temperature"] == 20 and calls[-1]["climate_enabled"] is False
        assert calls[-1]["driver"] == calls[-1]["passenger"] == 0
    asyncio.run(run())


def test_explicit_profile_uses_saved_values_without_changing_selection():
    async def run():
        calls=[]
        async def launch(**kwargs): calls.append(kwargs)
        obj=SimpleNamespace(preparation_profiles=profiles.initial_profiles(),
            card_settings={"selected_profile":"winter","temperature":31,"driver":1},
            feature_enabled=lambda feature:True,async_start_with_comfort=launch)
        before=dict(obj.card_settings)
        await start_method()(obj,profile_id="summer")
        assert calls[-1]["temperature"]==20 and calls[-1]["driver"]==0
        assert obj.card_settings==before
        obj.card_settings={}
        await start_method()(obj,profile_id="winter")
        assert calls[-1]["temperature"]==26 and calls[-1]["driver"]==3
        with pytest.raises(RuntimeError):await start_method()(obj,profile_id="deleted")
        assert len(calls)==2
    asyncio.run(run())


@pytest.mark.parametrize("settings", [{}, {"selected_profile":"deleted"}, {"selected_profile":"winter", "temperature":99}])
def test_missing_or_invalid_profile_never_launches(settings):
    obj=SimpleNamespace(preparation_profiles=profiles.initial_profiles(),card_settings=settings)
    with pytest.raises(RuntimeError): asyncio.run(start_method()(obj))


def test_button_availability_attributes_and_press():
    class Entity:
        def __init__(self, coordinator): self.coordinator=coordinator
        @property
        def available(self): return self.coordinator.last_update_success
    node=next(n for n in ast.parse((ROOT / "button.py").read_text(encoding="utf-8")).body
              if isinstance(n, ast.ClassDef) and n.name == "GwmJolionStartSelectedProfileButton")
    scope=dict(GwmJolionEntity=Entity, ButtonEntity=type("Button",(),{}), GwmJolionCoordinator=object, Any=object)
    exec(compile(ast.Module(body=[node],type_ignores=[]),"button","exec"),scope)
    calls=[]
    async def launch(**kwargs): calls.append(kwargs or "launch")
    obj=SimpleNamespace(entry_id="car-one",last_update_success=True,enable_remote_controls=True,security_pin="test",command_in_progress=False,
        preparation_profiles=profiles.initial_profiles(),card_settings={"selected_profile":"winter"},async_start_selected_profile=launch)
    button=scope[node.name](obj)
    assert button._attr_unique_id == "car-one_start_selected_profile"
    assert button.available and button.extra_state_attributes["selected_profile_name"] == "Зима"
    asyncio.run(button.async_press())
    assert calls == ["launch"]
    for field,value in [("command_in_progress",True),("last_update_success",False),("enable_remote_controls",False),("security_pin","")]:
        old=getattr(obj,field);setattr(obj,field,value)
        assert not button.available
        setattr(obj,field,old)
    obj.card_settings={}
    assert not button.available and button.extra_state_attributes["selected_profile_name"] is None
    named=scope[node.name](obj,profile_id="winter")
    assert named.available and named.name == "Запустить профиль: Зима"
    stable_id=named._attr_unique_id
    asyncio.run(named.async_press())
    assert calls[-1] == {"profile_id":"winter"}
    obj.preparation_profiles[0]["name"]="Мороз"
    assert named.name == "Запустить профиль: Мороз" and named._attr_unique_id == stable_id
    obj.preparation_profiles=[]
    assert not named.available


def test_profile_buttons_added_once_and_listener_unloaded():
    node=next(n for n in ast.parse((ROOT / "button.py").read_text(encoding="utf-8")).body
              if isinstance(n, ast.AsyncFunctionDef) and n.name == "async_setup_entry")
    listeners=[]
    cleanup=[]
    added=[]
    def subscribe(callback):
        listeners.append(callback)
        return lambda:listeners.remove(callback)
    obj=SimpleNamespace(enable_remote_controls=True,security_pin="test",
                        preparation_profiles=profiles.initial_profiles(),async_add_listener=subscribe)
    scope=dict(HomeAssistant=object,ConfigEntry=object,AddEntitiesCallback=object,DOMAIN="gwm",
               ButtonEntity=object,GwmJolionCoordinator=object,COMMANDS={},PUBLIC_COMMAND_BUTTON_KEYS=[],
               GwmJolionRefreshButton=lambda c:"refresh",
               GwmJolionStartSelectedProfileButton=lambda c,profile_id=None:profile_id or "selected")
    exec(compile(ast.Module(body=[node],type_ignores=[]),"setup","exec"),scope)
    asyncio.run(scope[node.name](SimpleNamespace(data={"gwm":{"car":obj}}),
                                SimpleNamespace(entry_id="car",async_on_unload=cleanup.append),added.extend))
    assert added == ["refresh","selected","winter","summer","driver"]
    listeners[0]()
    assert len(added)==5
    obj.preparation_profiles.append({"id":"custom","name":"Свой"})
    listeners[0]()
    assert added[-1]=="custom" and len(added)==6
    cleanup[0]()
    assert not listeners
