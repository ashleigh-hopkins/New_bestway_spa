from __future__ import annotations

import asyncio

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, Icon
from .entity import BestwayEntity

SWITCH_TYPES = [
    ("power_state", "Spa Power", Icon.POWER),
    ("filter_state", "Filter", Icon.FILTER),
    ("heater_state", "Heater", Icon.HEATER),
    ("hydrojet_state", "Hydrojet", Icon.HYDROJET),
    # wave_state removed - use select.bubble_mode instead for L1/L2/Off control
]


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
            BestwaySpaSwitch(
                coordinator,
                api,
                key,
                name,
                icon,
                entry.title,
                device_id,
                product_id,
                product_series,
            )
            for key, name, icon in SWITCH_TYPES
        ]
    )


class BestwaySpaSwitch(BestwayEntity, SwitchEntity):
    has_entity_name = True

    def __init__(
        self,
        coordinator,
        api,
        key,
        name,
        icon,
        title,
        device_id,
        product_id=None,
        product_series=None,
    ):
        super().__init__(coordinator, device_id, title, product_id, product_series)
        self._api = api
        self._key = key
        self._attr_translation_key = key
        self._attr_translation_placeholders = {"name": f"{title} {name}"}
        self._attr_unique_id = f"{device_id}_{key}"
        self._attr_icon = icon

    @property
    def is_on(self):
        if self._key == "filter_state":
            # API returns 2 when filter is active
            return self.coordinator.data.get("filter_state") == 2
        elif self._key == "heater_state":
            # Heater state values from device firmware:
            # 0=off, 2=reduced power (initial or with bubbles), 3=full power
            # 4=idle (at target), 5=reduced power (post-target), 6=full power (post-target)
            heater_state = self.coordinator.data.get("heater_state")
            return heater_state != 0
        else:
            return self.coordinator.data.get(self._key) == 1

    @property
    def extra_state_attributes(self):
        if self._key == "heater_state":
            heater_state = self.coordinator.data.get("heater_state", 0)

            # Determine heating status based on state
            if heater_state == 0:
                status = "off"
                actively_heating = False
            elif heater_state == 4:
                status = "idle_at_target"
                actively_heating = False
            elif heater_state in [2, 5]:
                status = "reduced_power"
                actively_heating = True
            elif heater_state in [3, 6]:
                status = "full_power"
                actively_heating = True
            else:
                status = f"unknown_{heater_state}"
                actively_heating = False

            return {
                "heating_status": status,
                "actively_heating": actively_heating,
                "heater_state_value": heater_state,
            }
        return {}

    async def async_turn_on(self):
        await self._api.set_state(self._key, 1)
        await asyncio.sleep(2)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self):
        await self._api.set_state(self._key, 0)
        await asyncio.sleep(2)
        await self.coordinator.async_request_refresh()
