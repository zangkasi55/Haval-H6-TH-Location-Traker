"""Local snapshot ingestion; never refreshes, signs into or controls the vehicle."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, RECORD, SOURCE_DEVICE
from .journey_storage import journey_store
from .map_state import recent_vehicle
from .source import SourceError, selected_snapshot, source_binding, source_coordinator

LOGGER = logging.getLogger(__name__)


class TrackerCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, LOGGER, name=DOMAIN, config_entry=entry, update_interval=timedelta(seconds=30))
        self.entry = entry
        self.history = journey_store(hass, entry.entry_id)
        self.history_error = False
        self._source: DataUpdateCoordinator[Any] | None = None
        self._unsubscribe: Callable[[], None] | None = None

    @callback
    def _source_updated(self) -> None:
        self.hass.async_create_task(self.async_request_refresh(), "Haval local source observation")

    def _bind(self, source: DataUpdateCoordinator[Any] | None) -> None:
        if self._source is source:
            return
        if self._unsubscribe is not None:
            self._unsubscribe()
        self._source = source
        self._unsubscribe = source.async_add_listener(self._source_updated) if source is not None else None

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            binding = source_binding(self.hass, self.entry.data[SOURCE_DEVICE])
            source = source_coordinator(self.hass, binding)
            self._bind(source)
            snapshot = selected_snapshot(source, binding)
        except SourceError as error:
            self._bind(None)
            raise UpdateFailed(str(error)) from error
        recording = self.entry.options.get(RECORD, self.entry.data.get(RECORD, False)) is True
        try:
            await self.history.record([snapshot] if snapshot is not None and recording else [])
            self.history_error = False
        except (OSError, ValueError) as error:
            self.history_error = True
            LOGGER.error("Private Haval observations could not be saved: type=%s", type(error).__name__)
        return {"current": recent_vehicle(snapshot), "recording": recording, "source_available": snapshot is not None}

    async def close(self) -> None:
        self._bind(None)
        await self.async_shutdown()
