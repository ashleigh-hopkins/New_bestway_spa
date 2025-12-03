from __future__ import annotations

from datetime import datetime

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, Icon
from .entity import BestwayEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    device_id = entry.title.lower().replace(" ", "_")
    product_id = entry.data.get("product_id")
    product_series = entry.data.get("product_series")

    async_add_entities(
        [
            ResetButton(
                coordinator,
                hass,
                entry,
                "Reset Filter Date",
                "filter_last_change",
                device_id,
                product_id,
                product_series,
            ),
            ResetButton(
                coordinator,
                hass,
                entry,
                "Reset Chlorine Date",
                "chlorine_last_add",
                device_id,
                product_id,
                product_series,
            ),
        ]
    )


class ResetButton(BestwayEntity, ButtonEntity):
    has_entity_name = True

    def __init__(
        self,
        coordinator,
        hass,
        entry,
        name,
        key,
        device_id,
        product_id=None,
        product_series=None,
    ):
        super().__init__(
            coordinator, device_id, entry.title, product_id, product_series
        )
        self._hass = hass
        self._entry = entry
        self._attr_translation_key = key
        self._attr_translation_placeholders = {"name": f"{name}"}
        self._key = key
        self._attr_icon = Icon.CALENDAR

    @property
    def unique_id(self):
        return f"{DOMAIN}_{self._key}_reset_{self._entry.entry_id}"

    async def async_press(self):
        new_date = datetime.now().strftime("%Y-%m-%d")
        self._hass.data[DOMAIN][self._entry.entry_id][self._key] = new_date

        data = dict(self._entry.data)
        data[self._key] = new_date
        self._hass.config_entries.async_update_entry(self._entry, data=data)

        self.coordinator.data[self._key] = new_date
        self.coordinator.async_update_listeners()
