"""Read-only local Haval journey companion for an existing GWM integration."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from homeassistant.components.http.server import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN, FRONTEND_PATH
from .coordinator import TrackerCoordinator
from .journey_storage import journey_store
from .journey_ws import register_journey_api

type TrackerConfigEntry = ConfigEntry[TrackerCoordinator]
PLATFORMS = [Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    lock = hass.data.setdefault(DOMAIN + "_frontend_lock", asyncio.Lock())
    async with lock:
        if not hass.data.get(DOMAIN + "_frontend_ready"):
            await hass.http.async_register_static_paths([
                StaticPathConfig(FRONTEND_PATH, str(Path(__file__).parent / "frontend"), cache_headers=False),
            ])
            register_journey_api(hass)
            hass.data[DOMAIN + "_frontend_ready"] = True
    for entry in hass.config_entries.async_entries(DOMAIN):
        await journey_store(hass, entry.entry_id).start()
    return True


async def async_setup_entry(hass: HomeAssistant, entry: TrackerConfigEntry) -> bool:
    coordinator = TrackerCoordinator(hass, entry)
    try:
        await coordinator.async_config_entry_first_refresh()
        entry.runtime_data = coordinator
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except BaseException:
        await coordinator.close()
        raise
    entry.async_on_unload(entry.add_update_listener(_reload))
    return True


async def _reload(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: TrackerConfigEntry) -> bool:
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    await entry.runtime_data.close()
    return True


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await journey_store(hass, entry.entry_id).remove()
