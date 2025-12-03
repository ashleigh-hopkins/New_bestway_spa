from __future__ import annotations

import asyncio
import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, Icon
from .entity import BestwayEntity

_LOGGER = logging.getLogger(__name__)

OPTIONS = ["OFF", "MEDIUM", "MAX"]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Bestway Spa bubble mode select entity."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    api = data["api"]
    device_id = entry.title.lower().replace(" ", "_")
    product_id = entry.data.get("product_id")
    product_series = entry.data.get("product_series")

    async_add_entities(
        [
            BestwaySpaBubbleSelect(
                coordinator, api, entry.title, device_id, product_id, product_series
            )
        ]
    )


class BestwaySpaBubbleSelect(BestwayEntity, SelectEntity):
    """Select entity to control the bubble mode of the Bestway Spa."""

    has_entity_name = True
    _attr_options = OPTIONS

    def __init__(
        self, coordinator, api, title, device_id, product_id=None, product_series=None
    ):
        super().__init__(coordinator, device_id, title, product_id, product_series)
        self._api = api
        self._attr_translation_key = "bubble_mode"
        self._attr_translation_placeholders = {"name": f"{title} Spa bubbles"}
        self._attr_unique_id = f"{device_id}_bubble_mode"
        self._attr_icon = Icon.BUBBLES

    @property
    def current_option(self):
        """Return the current bubble mode based on wave_state."""
        wave_state = self.coordinator.data.get("wave_state", 0)
        _LOGGER.debug(f"Current wave_state: {wave_state}")

        if wave_state == 0:
            return "OFF"
        elif wave_state == 100:
            return "MEDIUM"
        else:
            return "MAX"

    async def async_select_option(self, option: str):
        """Handle selection from user."""
        _LOGGER.debug(f"User selected bubble mode: {option}")

        if option == "OFF":
            await self._api.set_state("wave_state", 0)

        elif option == "MEDIUM":
            await self._api.set_state("wave_state", 0)
            await asyncio.sleep(1.5)
            await self._api.set_state("wave_state", 1)

        elif option == "MAX":
            await self._api.set_state("wave_state", 0)
            await asyncio.sleep(1.5)
            await self._api.set_state("wave_state", 1)
            await asyncio.sleep(1.5)
            await self._api.set_state("wave_state", 1)

        await self.coordinator.async_request_refresh()


__all__ = ["async_setup_entry"]
