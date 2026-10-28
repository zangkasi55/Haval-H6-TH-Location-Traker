import inspect
from datetime import timedelta
from types import MappingProxyType, SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
import pytest_asyncio
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from custom_components.haval_h6_th_location_tracker import journey_storage, journey_ws
from custom_components.haval_h6_th_location_tracker.const import DOMAIN, RECORD, SOURCE_DEVICE, VEHICLE_KEY
from custom_components.haval_h6_th_location_tracker.journey import ObservationError
from custom_components.haval_h6_th_location_tracker.journey_storage import JourneyStore, journey_store
from tests.python.test_journey import NOW, sample


@pytest_asyncio.fixture
async def hass(tmp_path):
    instance = HomeAssistant(str(tmp_path))
    yield instance
    await instance.async_block_till_done()
    await instance.async_stop(force=True)


def entry(record=True):
    return ConfigEntry(
        domain=DOMAIN, title="Synthetic Haval", version=1, minor_version=1,
        source="user", unique_id="synthetic-source", data={SOURCE_DEVICE: "source-device", RECORD: record},
        options={}, discovery_keys=MappingProxyType({}), subentries_data=None,
    )


def snapshot(seconds=0, **changes):
    observation = sample(seconds, **changes)
    return {
        "vin": VEHICLE_KEY,
        "timestamps": {"acquisition_time": observation.time.isoformat()},
        "location": observation.position,
        "values": {
            "soc": observation.soc, "locked": observation.locked,
            "door_front_driver_open": observation.doors[0],
        },
    }


async def test_cached_stale_and_out_of_order_cannot_extend_a_stop(hass):
    store = JourneyStore(hass, "synthetic-entry")
    for source, received in [(0, 0), (60, 60), (60, 120), (0, 120), (60, 900)]:
        await store.record([snapshot(source)], now=NOW + timedelta(seconds=received))
    result = await store.history(VEHICLE_KEY, 24, now=NOW + timedelta(seconds=900))
    assert result["sample_count"] == 2
    assert result["stops"][0]["observed_duration_seconds"] == 60
    assert result["status"] == "stale_sample"


async def test_history_survives_restart_and_creates_no_location_entity_attributes(hass):
    store = JourneyStore(hass, "synthetic-entry")
    await store.record([snapshot(0), snapshot(60)], now=NOW + timedelta(seconds=60))
    result = await JourneyStore(hass, "synthetic-entry").history(
        VEHICLE_KEY, 24, now=NOW + timedelta(seconds=60),
    )
    assert result["sample_count"] == 2 and result["stops"][0]["battery_arrival"] == 55
    assert not hass.states.async_entity_ids()


async def test_fixed_retention_expiry_does_not_need_a_fresh_cloud_observation(hass):
    store = journey_store(hass, "synthetic-entry")
    assert journey_store(hass, "synthetic-entry") is store
    await store.record([snapshot()], now=NOW)
    assert store.next_expiry == NOW + timedelta(days=7)
    await store._expire(NOW + timedelta(days=7))
    assert not (await store._load())[VEHICLE_KEY]
    assert store.next_expiry is None


async def test_retention_retries_and_reports_disk_errors(hass, monkeypatch):
    store = JourneyStore(hass, "synthetic-entry")
    await store.record([snapshot()], now=NOW)
    monkeypatch.setattr(store._store, "async_save", AsyncMock(side_effect=OSError("synthetic disk failure")))
    await store._expire(NOW + timedelta(days=7))
    assert store.retention_error
    assert store.next_expiry == NOW + timedelta(days=7, seconds=60)


async def test_failed_write_does_not_advance_the_in_memory_history(hass, monkeypatch):
    store = JourneyStore(hass, "synthetic-entry")
    monkeypatch.setattr(store._store, "async_save", AsyncMock(side_effect=OSError("synthetic disk failure")))
    with pytest.raises(OSError):
        await store.record([snapshot()], now=NOW)
    assert await store._load() == {}


async def test_corrupt_storage_is_not_silently_discarded(hass, monkeypatch):
    store = JourneyStore(hass, "synthetic-entry")
    monkeypatch.setattr(store._store, "async_load", AsyncMock(return_value={"vehicles": {"selected": [123]}}))
    with pytest.raises(ObservationError):
        await store.history(VEHICLE_KEY, 24, now=NOW)


async def test_cap_and_startup_pruning(hass, monkeypatch):
    monkeypatch.setattr(journey_storage, "MAX_SAMPLES", 3)
    store = JourneyStore(hass, "synthetic-entry")
    await store.record([snapshot(seconds) for seconds in (0, 60, 120, 180)], now=NOW + timedelta(seconds=180))
    assert len((await store._load())[VEHICLE_KEY]) == 3
    await store.history(VEHICLE_KEY, 24, now=NOW + timedelta(days=8))
    assert not (await JourneyStore(hass, "synthetic-entry")._load())[VEHICLE_KEY]


def permission_context(hass, monkeypatch, *, admin=True, active=True, companion_permission=True, source_permission=True):
    configured = entry()
    device = SimpleNamespace(
        id="tracker-device", config_entries={configured.entry_id},
        identifiers={(DOMAIN, configured.entry_id)},
    )
    user = SimpleNamespace(
        is_admin=admin, is_active=active,
        permissions=SimpleNamespace(check_entity=lambda entity, policy: (
            companion_permission if entity == "sensor.synthetic_tracker" else source_permission
        )),
    )
    connection = SimpleNamespace(user=user, send_result=Mock(), send_error=Mock())
    monkeypatch.setattr(journey_ws.dr, "async_get", lambda hass: SimpleNamespace(async_get=lambda id: device))
    monkeypatch.setattr(journey_ws.er, "async_get", lambda hass: object())
    monkeypatch.setattr(journey_ws.er, "async_entries_for_device", lambda registry, device_id: [
        SimpleNamespace(
            platform=DOMAIN if device_id == device.id else "gwm_thailand_connect",
            config_entry_id="source-entry", entity_id="sensor.synthetic_tracker" if device_id == device.id else "sensor.synthetic_soc",
        ),
    ])
    monkeypatch.setattr(hass, "config_entries", SimpleNamespace(async_entries=lambda domain: [configured]))
    monkeypatch.setattr(journey_ws, "source_binding", lambda *args: SimpleNamespace(
        domain="gwm_thailand_connect", entry_id="source-entry",
    ))
    return configured, connection


@pytest.mark.parametrize("changes", [
    {"admin": False}, {"active": False}, {"companion_permission": False}, {"source_permission": False},
])
async def test_history_requires_admin_and_both_device_permissions(hass, monkeypatch, changes):
    _, connection = permission_context(hass, monkeypatch, **changes)
    with pytest.raises(ValueError, match="not_authorized"):
        journey_ws.resolve_entry(hass, connection, "tracker-device")


async def test_history_can_be_read_after_tracker_unloads_without_cloud_login(hass, monkeypatch):
    configured, connection = permission_context(hass, monkeypatch)
    assert journey_ws.resolve_entry(hass, connection, "tracker-device") is configured
    assert not hasattr(configured, "runtime_data")


async def test_handlers_read_local_history_and_reject_nonliteral_deletion(hass, monkeypatch):
    configured, connection = permission_context(hass, monkeypatch)
    handlers = []
    monkeypatch.setattr(journey_ws.websocket_api, "async_register_command", lambda hass, handler: handlers.append(handler))
    journey_ws.register_journey_api(hass)
    assert len(handlers) == 2
    store = SimpleNamespace(
        history=AsyncMock(return_value={"sample_count": 0}), clear=AsyncMock(), retention_error=False,
    )
    monkeypatch.setattr(journey_ws, "journey_store", lambda *args: store)
    await inspect.unwrap(handlers[0])(hass, connection, {"id": 1, "device_id": "tracker-device", "hours": 24})
    store.history.assert_awaited_once_with(VEHICLE_KEY, 24)
    assert connection.send_result.call_args[0][1]["current"]["position"] is None
    for value in (False, 1, "true", None):
        await inspect.unwrap(handlers[1])(hass, connection, {"id": 2, "device_id": "tracker-device", "confirmed": value})
    store.clear.assert_not_called()
    await inspect.unwrap(handlers[1])(hass, connection, {"id": 3, "device_id": "tracker-device", "confirmed": True})
    store.clear.assert_awaited_once_with(VEHICLE_KEY)
    assert configured.data[SOURCE_DEVICE] == "source-device"


async def test_recording_disabled_does_not_return_hidden_old_history(hass, monkeypatch):
    configured, connection = permission_context(hass, monkeypatch)
    configured = entry(record=False)
    monkeypatch.setattr(journey_ws, "resolve_entry", lambda *args, **kwargs: configured)
    handlers = []
    monkeypatch.setattr(journey_ws.websocket_api, "async_register_command", lambda hass, handler: handlers.append(handler))
    journey_ws.register_journey_api(hass)
    store = SimpleNamespace(
        history=AsyncMock(return_value={"segments": [["private"]], "engine_code_changes": ["private"]}),
        retention_error=False,
    )
    monkeypatch.setattr(journey_ws, "journey_store", lambda *args: store)
    await inspect.unwrap(handlers[0])(hass, connection, {"id": 1, "device_id": "tracker-device", "hours": 24})
    result = connection.send_result.call_args[0][1]
    assert result["status"] == "disabled" and result["segments"] == []
    assert "private" not in str(result) and "engine_code_changes" not in result
