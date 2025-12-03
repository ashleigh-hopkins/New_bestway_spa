from __future__ import annotations

import asyncio

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, Icon
from .entity import BestwayEntity

C_TEMPS = {"min": 20, "max": 40}
F_TEMPS = {"min": 68, "max": 104}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    api = data["api"]
    device_id = entry.title.lower().replace(" ", "_")
    product_id = entry.data.get("product_id")
    product_series = entry.data.get("product_series")

    async_add_entities(
        [
            BestwaySpaTargetTemperature(
                coordinator, api, entry.title, device_id, product_id, product_series
            )
        ]
    )


class BestwaySpaTargetTemperature(BestwayEntity, NumberEntity):
    has_entity_name = True

    def __init__(
        self, coordinator, api, title, device_id, product_id=None, product_series=None
    ):
        super().__init__(coordinator, device_id, title, product_id, product_series)
        self._api = api
        self._attr_translation_key = "temperature_setting"
        self._attr_translation_placeholders = {"name": f"{title} Target Temperature"}
        self._attr_unique_id = f"{device_id}_temperature_setting"
        self._attr_device_class = "temperature"
        self._attr_native_step = 1.0
        self._attr_icon = Icon.THERMOMETER

    @property
    def native_value(self):
        return self.coordinator.data.get("temperature_setting")

    @property
    def native_unit_of_measurement(self):
        unit_code = self.coordinator.data.get("temperature_unit", 1)
        return (
            UnitOfTemperature.FAHRENHEIT
            if unit_code == 0
            else UnitOfTemperature.CELSIUS
        )

    @property
    def native_min_value(self):
        unit_code = self.coordinator.data.get("temperature_unit", 1)
        return F_TEMPS["min"] if unit_code == 0 else C_TEMPS["min"]

    @property
    def native_max_value(self):
        unit_code = self.coordinator.data.get("temperature_unit", 1)
        return F_TEMPS["max"] if unit_code == 0 else C_TEMPS["max"]

    async def async_set_native_value(self, value: float):
        await self._api.set_state("temperature_setting", value)
        await asyncio.sleep(2)
        await self.coordinator.async_request_refresh()
