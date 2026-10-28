from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from custom_components.haval_h6_th_location_tracker import source
from custom_components.haval_h6_th_location_tracker.const import DOMAIN, RECORD, SOURCE_DEVICE, VEHICLE_KEY
from custom_components.haval_h6_th_location_tracker.coordinator import TrackerCoordinator
from custom_components.haval_h6_th_location_tracker.source import SourceBinding, SourceError, selected_snapshot
from tests.python.test_journey_storage import entry, snapshot
from tests.python.test_journey_storage import hass as hass

BINDING = SourceBinding("source-entry", "gwm_thailand_connect", "SYNTHETICVIN")


def source_runtime():
    data = snapshot()
    data.update(vin=BINDING.identifier, access_token="synthetic-never-copy", nickname="private")
    return SimpleNamespace(
        data={"vehicles": [data]}, last_update_success=True,
        async_request_refresh=AsyncMock(side_effect=AssertionError("No cloud request is allowed")),
    )


def test_source_projection_discards_identifiers_and_unrelated_data():
    runtime = source_runtime()
    data = selected_snapshot(runtime, BINDING)
    assert data["vin"] == VEHICLE_KEY
    assert data["values"]["soc"] == 55
    assert "SYNTHETICVIN" not in str(data) and "synthetic-never-copy" not in str(data) and "private" not in str(data)
    data["values"]["soc"] = 1
    assert runtime.data["vehicles"][0]["values"]["soc"] == 55


def test_failed_unloaded_or_missing_vehicle_never_reuses_a_cached_current_fix():
    runtime = source_runtime()
    runtime.last_update_success = False
    assert selected_snapshot(runtime, BINDING) is None
    assert selected_snapshot(None, BINDING) is None
    runtime.last_update_success = True
    runtime.data["vehicles"][0]["vin"] = "DIFFERENT-SYNTHETICVIN"
    assert selected_snapshot(runtime, BINDING) is None


@pytest.mark.parametrize("data", [{}, {"vehicles": "wrong"}, {"vehicles": [
    {"vin": "SYNTHETICVIN", "timestamps": [], "values": {}},
]}])
def test_unsupported_source_contract_fails_explicitly(data):
    with pytest.raises(SourceError):
        selected_snapshot(SimpleNamespace(data=data, last_update_success=True), BINDING)


@pytest.mark.parametrize("legacy", [False, True])
async def test_supported_coordinator_shapes_and_unload(hass, monkeypatch, legacy):
    import logging

    coordinator = DataUpdateCoordinator(hass, logging.getLogger(__name__), name="synthetic-source", config_entry=None)
    runtime = SimpleNamespace(coordinator=coordinator) if legacy else coordinator
    configured = SimpleNamespace(domain=BINDING.domain, state=ConfigEntryState.LOADED, runtime_data=runtime)
    monkeypatch.setattr(hass, "config_entries", SimpleNamespace(async_get_entry=lambda id: configured))
    assert source.source_coordinator(hass, BINDING) is coordinator
    configured.state = ConfigEntryState.NOT_LOADED
    assert source.source_coordinator(hass, BINDING) is None


async def test_device_entry_and_region_binding_are_not_guessed(hass, monkeypatch):
    device = SimpleNamespace(
        identifiers={("gwm_ora", "SYNTHETICVIN")}, config_entries={"source-entry"},
    )
    configured = SimpleNamespace(entry_id="source-entry", data={"region": "tha"})
    monkeypatch.setattr(source.dr, "async_get", lambda hass: SimpleNamespace(async_get=lambda id: device))
    monkeypatch.setattr(hass, "config_entries", SimpleNamespace(async_entries=lambda domain: [configured]))
    assert source.source_binding(hass, "source-device").identifier == "SYNTHETICVIN"
    configured.data["region"] = "eu"
    with pytest.raises(SourceError):
        source.source_binding(hass, "source-device")


async def test_companion_only_reads_local_cache_and_respects_recording_opt_in(hass, monkeypatch):
    import custom_components.haval_h6_th_location_tracker.coordinator as module

    configured = entry(record=False)
    runtime = source_runtime()
    monkeypatch.setattr(module, "source_binding", lambda *args: BINDING)
    monkeypatch.setattr(module, "source_coordinator", lambda *args: runtime)
    monkeypatch.setattr(runtime, "async_add_listener", lambda callback: lambda: None, raising=False)
    coordinator = TrackerCoordinator(hass, configured)
    coordinator.history.record = AsyncMock()
    result = await coordinator._async_update_data()
    coordinator.history.record.assert_awaited_once_with([])
    runtime.async_request_refresh.assert_not_called()
    assert result["recording"] is False
    configured = entry(record=True)
    assert configured.data[RECORD] is True and configured.data[SOURCE_DEVICE] == "source-device"
    assert BINDING.domain != DOMAIN
    await coordinator.close()


async def test_storage_error_is_visible_without_reclassifying_missing_power(hass, monkeypatch):
    import custom_components.haval_h6_th_location_tracker.coordinator as module

    runtime = source_runtime()
    runtime.async_add_listener = lambda callback: lambda: None
    monkeypatch.setattr(module, "source_binding", lambda *args: BINDING)
    monkeypatch.setattr(module, "source_coordinator", lambda *args: runtime)
    coordinator = TrackerCoordinator(hass, entry())
    coordinator.history.record = AsyncMock(side_effect=OSError("synthetic disk failure"))
    await coordinator._async_update_data()
    assert coordinator.history_error is True
    await coordinator.close()
