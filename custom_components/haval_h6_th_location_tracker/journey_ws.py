"""Admin and per-source-device authorization for precise local observations."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import probatio as vol
else:
    import voluptuous as vol

from homeassistant.auth.permissions.const import POLICY_CONTROL, POLICY_READ
from homeassistant.components import websocket_api
from homeassistant.components.websocket_api.connection import ActiveConnection
from homeassistant.components.websocket_api.decorators import async_response, websocket_command
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN, RECORD, SOURCE_DEVICE, VEHICLE_KEY
from .coordinator import TrackerCoordinator
from .journey_storage import journey_store
from .source import source_binding

LOGGER = logging.getLogger(__name__)


def resolve_entry(
    hass: HomeAssistant, connection: ActiveConnection, device_id: str, *, write: bool = False,
) -> ConfigEntry:
    device = dr.async_get(hass).async_get(device_id)
    if device is None:
        raise ValueError("vehicle_not_found")
    user = connection.user
    if not user.is_active or not user.is_admin:
        raise ValueError("not_authorized")
    registry = er.async_get(hass)
    policy = POLICY_CONTROL if write else POLICY_READ
    if not any(
        entity.platform == DOMAIN and user.permissions.check_entity(entity.entity_id, policy)
        for entity in er.async_entries_for_device(registry, device.id)
    ):
        raise ValueError("not_authorized")
    entries = [
        entry for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.entry_id in device.config_entries and (DOMAIN, entry.entry_id) in device.identifiers
    ]
    if len(entries) != 1:
        raise ValueError("vehicle_not_found")
    entry = entries[0]
    binding = source_binding(hass, entry.data[SOURCE_DEVICE])
    if not any(
        entity.platform == binding.domain and entity.config_entry_id == binding.entry_id
        and user.permissions.check_entity(entity.entity_id, POLICY_READ)
        for entity in er.async_entries_for_device(registry, entry.data[SOURCE_DEVICE])
    ):
        raise ValueError("not_authorized")
    return entry


def register_journey_api(hass: HomeAssistant) -> None:
    if hass.data.get(DOMAIN + "_journey_api"):
        return

    @websocket_command({
        vol.Required("type"): DOMAIN + "/journeys",
        vol.Required("device_id"): str,
        vol.Optional("hours", default=24): vol.All(int, vol.Range(min=1, max=168)),
        vol.Optional("refresh_cloud", default=False): bool,
    })
    @async_response
    async def history(hass: HomeAssistant, connection: ActiveConnection, message: dict[str, Any]) -> None:
        try:
            entry = resolve_entry(hass, connection, message["device_id"])
        except ValueError as error:
            connection.send_error(message["id"], str(error), "Selected vehicle history is not accessible")
            return
        if type(message.get("refresh_cloud", False)) is not bool:
            connection.send_error(message["id"], "invalid_refresh_option", "Refresh must be a boolean")
            return
        runtime = getattr(entry, "runtime_data", None)
        coordinator = runtime if isinstance(runtime, TrackerCoordinator) else None
        if coordinator is not None and message.get("refresh_cloud") is True:
            await coordinator.async_request_refresh()
            if not coordinator.last_update_success:
                connection.send_error(message["id"], "source_read_failed", "The local source could not be read")
                return
        current = coordinator.data["current"] if coordinator and coordinator.data and coordinator.last_update_success else {
            "availability": "source_unavailable", "position": None,
        }
        recording = entry.options.get(RECORD, entry.data.get(RECORD, False)) is True
        store = journey_store(hass, entry.entry_id)
        try:
            result = await store.history(VEHICLE_KEY, message["hours"])
        except (OSError, ValueError) as error:
            LOGGER.error("Private history read failed: type=%s", type(error).__name__)
            connection.send_error(message["id"], "history_storage_failed", "Private journey history could not be read")
            return
        if not recording:
            result = {
                "status": "disabled", "segments": [], "stops": [], "doors": [],
                "sample_count": 0, "retention_days": 7,
            }
        result.update(
            current=current,
            storage_warning=store.retention_error or (coordinator is not None and coordinator.history_error),
        )
        connection.send_result(message["id"], result)

    @websocket_command({
        vol.Required("type"): DOMAIN + "/clear_journeys",
        vol.Required("device_id"): str,
        vol.Required("confirmed"): vol.In([True]),
    })
    @async_response
    async def clear(hass: HomeAssistant, connection: ActiveConnection, message: dict[str, Any]) -> None:
        if message["confirmed"] is not True:
            connection.send_error(message["id"], "confirmation_required", "Confirm local history deletion")
            return
        try:
            entry = resolve_entry(hass, connection, message["device_id"], write=True)
        except ValueError as error:
            connection.send_error(message["id"], str(error), "Selected vehicle history is not accessible")
            return
        try:
            await journey_store(hass, entry.entry_id).clear(VEHICLE_KEY)
        except (OSError, ValueError) as error:
            LOGGER.error("Private history deletion failed: type=%s", type(error).__name__)
            connection.send_error(message["id"], "history_storage_failed", "Private journey history could not be cleared")
            return
        connection.send_result(message["id"], {"cleared": True})

    websocket_api.async_register_command(hass, history)
    websocket_api.async_register_command(hass, clear)
    hass.data[DOMAIN + "_journey_api"] = True
