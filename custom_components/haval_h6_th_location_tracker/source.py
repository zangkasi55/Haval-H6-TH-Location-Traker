"""Read only the selected vehicle's normalized, already-loaded GWM snapshot."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import SOURCE_DOMAINS, VEHICLE_KEY
from .journey import DOORS

VALUE_KEYS = (*DOORS, "soc", "odometer_km", "locked", "ac_active", "engine_state_code", "vehicle_power_off")


class SourceError(ValueError):
    """A bounded, non-secret reason for rejecting a source contract."""


@dataclass(frozen=True)
class SourceBinding:
    entry_id: str
    domain: str
    identifier: str = field(repr=False)


def source_binding(hass: HomeAssistant, device_id: str) -> SourceBinding:
    device = dr.async_get(hass).async_get(device_id)
    if device is None:
        raise SourceError("source_not_found")
    candidates = [
        SourceBinding(entry.entry_id, domain, identifier)
        for domain, identifier in device.identifiers
        if domain in SOURCE_DOMAINS and isinstance(identifier, str) and identifier
        for entry in hass.config_entries.async_entries(domain)
        if entry.entry_id in device.config_entries
        and (domain != "gwm_ora" or entry.data.get("region") == "tha")
    ]
    if len(candidates) != 1:
        raise SourceError("source_not_supported")
    return candidates[0]


def source_coordinator(hass: HomeAssistant, binding: SourceBinding) -> DataUpdateCoordinator[Any] | None:
    entry = hass.config_entries.async_get_entry(binding.entry_id)
    if entry is None or entry.domain != binding.domain or entry.state is not ConfigEntryState.LOADED:
        return None
    runtime = getattr(entry, "runtime_data", None)
    coordinator = runtime if isinstance(runtime, DataUpdateCoordinator) else getattr(runtime, "coordinator", None)
    return coordinator if isinstance(coordinator, DataUpdateCoordinator) else None


def selected_snapshot(
    coordinator: DataUpdateCoordinator[Any] | None, binding: SourceBinding,
) -> dict[str, Any] | None:
    if coordinator is None or not coordinator.last_update_success:
        return None
    data = coordinator.data
    if not isinstance(data, dict) or not isinstance(data.get("vehicles"), list):
        raise SourceError("source_schema_unsupported")
    matches = [
        item for item in data["vehicles"]
        if isinstance(item, dict) and item.get("vin") == binding.identifier
    ]
    if not matches:
        return None
    if len(matches) != 1:
        raise SourceError("source_vehicle_ambiguous")
    vehicle = matches[0]
    timestamps, values, location = (vehicle.get(key) for key in ("timestamps", "values", "location"))
    if not isinstance(timestamps, dict) or not isinstance(values, dict) or (
        location is not None and not isinstance(location, dict)
    ):
        raise SourceError("source_schema_unsupported")
    return {
        "vin": VEHICLE_KEY,
        "timestamps": {key: timestamps.get(key) for key in ("acquisition_time", "update_time")},
        "values": {key: values.get(key) for key in VALUE_KEYS},
        "location": {key: location.get(key) for key in ("latitude", "longitude")} if location else None,
    }
