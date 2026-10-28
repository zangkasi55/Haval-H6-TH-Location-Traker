"""A non-location status entity used to discover this companion's private card."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import TrackerConfigEntry
from .const import DOMAIN, NAME
from .coordinator import TrackerCoordinator


class TrackerStatus(CoordinatorEntity[TrackerCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "journey_status"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["recording", "recording_off", "source_unavailable", "history_storage_error"]

    def __init__(self, coordinator: TrackerCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = coordinator.entry.entry_id + "_status"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.entry_id)}, name=NAME,
            manufacturer="Community", model="Read-only GWM journey companion",
        )

    @property
    def native_value(self) -> str:
        data = self.coordinator.data
        if self.coordinator.history_error or self.coordinator.history.retention_error:
            return "history_storage_error"
        if not data or data["source_available"] is not True:
            return "source_unavailable"
        return "recording" if data["recording"] else "recording_off"


async def async_setup_entry(
    hass: HomeAssistant, entry: TrackerConfigEntry, async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([TrackerStatus(entry.runtime_data)])
