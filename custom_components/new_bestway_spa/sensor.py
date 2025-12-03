from __future__ import annotations

from datetime import datetime, date

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import BestwayEntity

SENSOR_TYPES = [
    ("water_temperature", "Water Temperature"),
    ("is_online", "Connection Status"),
    ("temperature_unit", "Temperature Unit"),
    ("warning", "Warning"),
    ("error_code", "Error Code"),
    ("hydrojet_state", "Hydrojet"),
    ("connect_type", "Connection Type"),
    ("wifi_version", "WiFi Version"),
    ("ota_status", "OTA Status"),
    ("mcu_version", "MCU Version"),
    ("trd_version", "TRD Version"),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    device_id = entry.title.lower().replace(" ", "_")
    product_id = entry.data.get("product_id")
    product_series = entry.data.get("product_series")

    basic_sensors = [
        BestwaySpaSensor(
            coordinator, key, name, entry.title, device_id, product_id, product_series
        )
        for key, name in SENSOR_TYPES
    ]
    days_sensors = [
        DaysSinceSensor(
            coordinator,
            entry,
            "Filter",
            "filter_last_change",
            device_id,
            product_id,
            product_series,
        ),
        DaysSinceSensor(
            coordinator,
            entry,
            "Chlorine",
            "chlorine_last_add",
            device_id,
            product_id,
            product_series,
        ),
    ]
    async_add_entities([*basic_sensors, *days_sensors])


class BestwaySpaSensor(BestwayEntity, SensorEntity):
    has_entity_name = True

    def __init__(
        self,
        coordinator,
        key,
        name,
        title,
        device_id,
        product_id=None,
        product_series=None,
    ):
        super().__init__(coordinator, device_id, title, product_id, product_series)
        self._key = key
        self._attr_translation_key = key
        self._attr_translation_placeholders = {"name": f"{title} {name}"}
        self._attr_unique_id = f"{device_id}_{key}"

        # enable long-term statistics for water temperature
        if self._key == "water_temperature":
            self._attr_device_class = "temperature"
            self._attr_state_class = "measurement"

    @property
    def native_value(self):
        if self._key == "temperature_unit":
            raw = self.coordinator.data.get("temperature_unit", 1)
            return (
                UnitOfTemperature.FAHRENHEIT if raw == 0 else UnitOfTemperature.CELSIUS
            )
        return self.coordinator.data.get(self._key)

    @property
    def native_unit_of_measurement(self):
        if self._key == "water_temperature":
            unit_code = self.coordinator.data.get("temperature_unit", 1)
            return (
                UnitOfTemperature.FAHRENHEIT
                if unit_code == 0
                else UnitOfTemperature.CELSIUS
            )
        return None


class DaysSinceSensor(BestwayEntity, SensorEntity):
    has_entity_name = True

    def __init__(
        self,
        coordinator,
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
        self._entry = entry
        self._attr_translation_key = key
        self._attr_translation_placeholders = {
            "name": f"{entry.title} Days Since {name}"
        }
        self._key = key
        self._attr_unique_id = f"{device_id}_{key}_days_since"
        self._attr_native_unit_of_measurement = UnitOfTime.DAYS
        self._attr_device_class = "duration"
        self._attr_state_class = "total_increasing"

    @property
    def native_value(self):
        stored_date_str = self._entry.data.get(self._key)
        if not stored_date_str:
            return None
        try:
            stored_date = datetime.strptime(stored_date_str, "%Y-%m-%d").date()
            return (date.today() - stored_date).days
        except (ValueError, TypeError):
            return None
