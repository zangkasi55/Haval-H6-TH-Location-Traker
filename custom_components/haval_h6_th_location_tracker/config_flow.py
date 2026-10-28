"""Select an existing vehicle; there is no cloud sign-in or credential form."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import probatio as vol
else:
    import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import selector

from .const import DOMAIN, NAME, RECORD, SOURCE_DEVICE, SOURCE_DOMAINS
from .source import SourceError, source_binding


class HavalTrackerFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> HavalTrackerOptions:
        return HavalTrackerOptions()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                source_binding(self.hass, user_input[SOURCE_DEVICE])
            except SourceError:
                errors["base"] = "source_not_supported"
            else:
                await self.async_set_unique_id(user_input[SOURCE_DEVICE])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=NAME, data=user_input)
        registry = dr.async_get(self.hass)
        if not any(domain in SOURCE_DOMAINS for device in registry.devices for domain, _ in device.identifiers):
            return self.async_abort(reason="source_missing")
        return self.async_show_form(
            step_id="user", errors=errors,
            data_schema=vol.Schema({
                vol.Required(SOURCE_DEVICE): selector.DeviceSelector(selector.DeviceSelectorConfig(
                    filter=[{"integration": domain} for domain in SOURCE_DOMAINS],
                )),
                vol.Required(RECORD, default=False): bool,
            }),
        )


class HavalTrackerOptions(config_entries.OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(
                    RECORD, default=self.config_entry.options.get(
                        RECORD, self.config_entry.data.get(RECORD, False),
                    ),
                ): bool,
            }),
        )
