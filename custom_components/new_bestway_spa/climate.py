from homeassistant.const import UnitOfTemperature
from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import ClimateEntityFeature, HVACMode, HVACAction
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN
import logging
import asyncio

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    api = data["api"]

    device_id = entry.title.lower().replace(' ', '_')
    async_add_entities([BestwaySpaThermostat(coordinator, api, entry.title, device_id, hass)])


class BestwaySpaThermostat(CoordinatorEntity, ClimateEntity):
    has_entity_name = True
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_target_temperature_step = 1  # Only whole degrees supported

    def __init__(self, coordinator, api, title, device_id, hass):
        super().__init__(coordinator)
        self._api = api
        self._attr_translation_key = "thermostat"
        self._attr_translation_placeholders = {"name": f"{title} Thermostat"}
        self._attr_unique_id = f"{device_id}_thermostat"
        self._device_id = device_id
        self._device_name = title
        self.hass = hass

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._device_id)},
            "name": self._device_name,
            "manufacturer": "Bestway",
            "model": "Spa",
        }

    @property
    def current_temperature(self):
        return self.coordinator.data.get("water_temperature")

    @property
    def target_temperature(self):
        return self.coordinator.data.get("temperature_setting")

    @property
    def temperature_unit(self):
        unit_code = self.coordinator.data.get("temperature_unit", 1)
        return UnitOfTemperature.FAHRENHEIT if unit_code == 0 else UnitOfTemperature.CELSIUS

    @property
    def min_temp(self):
        unit_code = self.coordinator.data.get("temperature_unit", 1)
        return 68 if unit_code == 0 else 20
    
    @property
    def max_temp(self):
        unit_code = self.coordinator.data.get("temperature_unit", 1)
        return 104 if unit_code == 0 else 40

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return 1.0

    @property
    def hvac_mode(self):
        heater_state = self.coordinator.data.get("heater_state")
        power_state = self.coordinator.data.get("power_state")
        _LOGGER.debug(f"Heater state: {heater_state}, Power state: {power_state}")

        if heater_state is None or power_state != 1:
            return HVACMode.OFF

        is_heating = heater_state != 0
        _LOGGER.debug(f"Heater is actively heating (state {heater_state}): {is_heating}")
        return HVACMode.HEAT if is_heating else HVACMode.OFF

    @property
    def hvac_action(self):
        """Return current HVAC action (heating, idle, or off)."""
        heater_state = self.coordinator.data.get("heater_state")
        power_state = self.coordinator.data.get("power_state")

        if not heater_state or power_state != 1:
            return HVACAction.OFF

        # States 2,3,5,6 = actively heating
        # State 4 = idle at target
        # State 0 = off
        if heater_state in [2, 3, 5, 6]:
            return HVACAction.HEATING
        elif heater_state == 4:
            return HVACAction.IDLE
        else:
            return HVACAction.OFF

    async def async_set_temperature(self, **kwargs):
        temperature = kwargs.get("temperature")
        if temperature is not None:
            await self._api.set_state("temperature_setting", int(temperature))
            await asyncio.sleep(2)
            await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode):
        if hvac_mode == HVACMode.HEAT:
            await self._api.set_state("heater_state", 1)
        elif hvac_mode == HVACMode.OFF:
            await self._api.set_state("heater_state", 0)
            await asyncio.sleep(2)
            await self.coordinator.async_request_refresh()

__all__ = ["async_setup_entry"]
