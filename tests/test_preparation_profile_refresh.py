"""Regressions for local profile updates; no vehicle client is attached."""
import asyncio

from test_preparation_profiles import coordinator, profiles


def test_updating_selected_profile_refreshes_persisted_and_runtime_settings():
    async def run():
        obj = coordinator()
        await obj.async_load_profiles()
        await obj.async_manage_profile("select", profile_id="winter")
        await obj.async_save_card_settings({"comfort_start": False})
        settings = {**profiles.DEFAULT_SETTINGS, "temperature": 24, "climate_time": 10}
        await obj.async_manage_profile("update", profile_id="winter", name="Updated winter", settings=settings)
        assert {key: obj.card_settings[key] for key in settings} == settings
        assert obj.card_settings["selected_profile"] == "winter"
        assert obj.card_settings["comfort_start"] is False
        assert obj.climate_target_temperature == 24
        assert obj.climate_operation_time == 10
        restarted = coordinator(obj._profiles_store, obj._card_settings_store)
        await restarted.async_load_profiles()
        await restarted.async_load_card_settings()
        assert restarted.card_settings == obj.card_settings
    asyncio.run(run())
