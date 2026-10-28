from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from homeassistant.data_entry_flow import FlowResultType

import custom_components.haval_h6_th_location_tracker as integration
from custom_components.haval_h6_th_location_tracker import config_flow
from custom_components.haval_h6_th_location_tracker.const import DOMAIN, RECORD, SOURCE_DEVICE
from custom_components.haval_h6_th_location_tracker.coordinator import TrackerCoordinator
from custom_components.haval_h6_th_location_tracker.sensor import TrackerStatus
from custom_components.haval_h6_th_location_tracker.source import SourceError
from tests.python.test_journey_storage import entry
from tests.python.test_journey_storage import hass as hass


def flow(hass):
    result = config_flow.HavalTrackerFlow()
    result.hass, result.flow_id, result.handler = hass, "synthetic-flow", DOMAIN
    result.context = {"source": "user"}
    return result


async def test_setup_without_a_source_aborts_without_login_or_network(hass, monkeypatch):
    monkeypatch.setattr(config_flow.dr, "async_get", lambda hass: SimpleNamespace(devices=[]))
    result = await flow(hass).async_step_user()
    assert result["type"] is FlowResultType.ABORT and result["reason"] == "source_missing"


async def test_source_form_has_no_credential_or_vehicle_command_fields(hass, monkeypatch):
    device = SimpleNamespace(identifiers={("gwm_thailand_connect", "SYNTHETICVIN")})
    monkeypatch.setattr(config_flow.dr, "async_get", lambda hass: SimpleNamespace(devices=[device]))
    result = await flow(hass).async_step_user()
    assert result["type"] is FlowResultType.FORM
    assert {marker.schema for marker in result["data_schema"].schema} == {SOURCE_DEVICE, RECORD}


async def test_setup_stores_only_device_selection_and_opt_in(hass, monkeypatch):
    selected = flow(hass)
    monkeypatch.setattr(config_flow, "source_binding", lambda *args: object())
    monkeypatch.setattr(selected, "async_set_unique_id", AsyncMock())
    monkeypatch.setattr(selected, "_abort_if_unique_id_configured", Mock())
    result = await selected.async_step_user({SOURCE_DEVICE: "source-device", RECORD: True})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {SOURCE_DEVICE: "source-device", RECORD: True}
    selected.async_set_unique_id.assert_awaited_once_with("source-device")


async def test_unsupported_source_is_an_explicit_form_error(hass, monkeypatch):
    monkeypatch.setattr(config_flow, "source_binding", Mock(side_effect=SourceError("source_not_supported")))
    device = SimpleNamespace(identifiers={("gwm_thailand_connect", "SYNTHETICVIN")})
    monkeypatch.setattr(config_flow.dr, "async_get", lambda hass: SimpleNamespace(devices=[device]))
    result = await flow(hass).async_step_user({SOURCE_DEVICE: "wrong-device", RECORD: False})
    assert result["errors"] == {"base": "source_not_supported"}


async def test_setup_unload_and_remove_preserve_source_and_clean_only_local_history(hass, monkeypatch):
    configured = entry()
    coordinator = SimpleNamespace(
        async_config_entry_first_refresh=AsyncMock(), close=AsyncMock(),
    )
    store = SimpleNamespace(remove=AsyncMock())
    monkeypatch.setattr(integration, "TrackerCoordinator", lambda *args: coordinator)
    monkeypatch.setattr(integration, "journey_store", lambda *args: store)
    monkeypatch.setattr(configured, "async_on_unload", Mock())
    monkeypatch.setattr(configured, "add_update_listener", Mock(return_value=lambda: None))
    setups, unloads = AsyncMock(), AsyncMock(return_value=True)
    monkeypatch.setattr(hass, "config_entries", SimpleNamespace(
        async_forward_entry_setups=setups, async_unload_platforms=unloads,
    ))
    assert await integration.async_setup_entry(hass, configured)
    assert configured.runtime_data is coordinator
    setups.assert_awaited_once()
    assert await integration.async_unload_entry(hass, configured)
    coordinator.close.assert_awaited_once()
    await integration.async_remove_entry(hass, configured)
    store.remove.assert_awaited_once()
    assert configured.data[SOURCE_DEVICE] == "source-device"


async def test_failed_setup_closes_its_listener(hass, monkeypatch):
    coordinator = SimpleNamespace(
        async_config_entry_first_refresh=AsyncMock(side_effect=RuntimeError("synthetic setup error")),
        close=AsyncMock(),
    )
    monkeypatch.setattr(integration, "TrackerCoordinator", lambda *args: coordinator)
    with pytest.raises(RuntimeError, match="synthetic setup"):
        await integration.async_setup_entry(hass, entry())
    coordinator.close.assert_awaited_once()


async def test_status_sensor_never_has_location_or_route_attributes(hass):
    coordinator = TrackerCoordinator(hass, entry())
    coordinator.async_set_updated_data({"recording": True, "source_available": True, "current": {"position": None}})
    sensor = TrackerStatus(coordinator)
    assert sensor.native_value == "recording"
    assert sensor.extra_state_attributes is None
    coordinator.data["source_available"] = False
    assert sensor.native_value == "source_unavailable"
    coordinator.history_error = True
    assert sensor.native_value == "history_storage_error"
    await coordinator.close()
