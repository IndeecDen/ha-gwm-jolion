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
    async def launch(): calls.append("launch")
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
