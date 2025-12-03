"""Binary sensor platform for Bestway Spa integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import BestwayEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Bestway Spa binary sensors."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    device_id = entry.title.lower().replace(" ", "_")
    product_id = entry.data.get("product_id")
    product_series = entry.data.get("product_series")

    async_add_entities(
        [
            BestwayConnectivitySensor(
                coordinator, device_id, entry.title, product_id, product_series
            ),
            BestwayErrorSensor(
                coordinator, device_id, entry.title, product_id, product_series
            ),
            BestwayActivelyHeatingSensor(
                coordinator, device_id, entry.title, product_id, product_series
            ),
        ]
    )


class BestwayConnectivitySensor(BestwayEntity, BinarySensorEntity):
    """Binary sensor for spa connectivity status."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator,
        device_id: str,
        device_name: str,
        product_id: str | None = None,
        product_series: str | None = None,
    ) -> None:
        """Initialize connectivity sensor."""
        super().__init__(
            coordinator, device_id, device_name, product_id, product_series
        )
        self._attr_translation_key = "connected"
        self._attr_unique_id = f"{device_id}_connectivity"

    @property
    def is_on(self) -> bool:
        """Return true if spa is online."""
        return self.coordinator.data.get("is_online", False)


class BestwayErrorSensor(BestwayEntity, BinarySensorEntity):
    """Binary sensor for spa error status."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator,
        device_id: str,
        device_name: str,
        product_id: str | None = None,
        product_series: str | None = None,
    ) -> None:
        """Initialize error sensor."""
        super().__init__(
            coordinator, device_id, device_name, product_id, product_series
        )
        self._attr_translation_key = "errors"
        self._attr_unique_id = f"{device_id}_errors"

    @property
    def is_on(self) -> bool:
        """Return true if error or warning detected."""
        error_code = self.coordinator.data.get("error_code", 0)
        warning = self.coordinator.data.get("warning", 0)
        return error_code != 0 or warning != 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return error details as attributes."""
        error_code = self.coordinator.data.get("error_code", 0)
        warning = self.coordinator.data.get("warning", 0)

        attributes = {
            "error_code": error_code,
            "warning": warning,
        }

        # Add human-readable status
        if error_code != 0:
            attributes["status"] = f"Error: E{error_code:02d}"
        elif warning != 0:
            attributes["status"] = f"Warning: {warning}"
        else:
            attributes["status"] = "OK"

        return attributes


class BestwayActivelyHeatingSensor(BestwayEntity, BinarySensorEntity):
    """Binary sensor for active heating status."""

    _attr_device_class = BinarySensorDeviceClass.HEAT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator,
        device_id: str,
        device_name: str,
        product_id: str | None = None,
        product_series: str | None = None,
    ) -> None:
        """Initialize heating sensor."""
        super().__init__(
            coordinator, device_id, device_name, product_id, product_series
        )
        self._attr_translation_key = "actively_heating"
        self._attr_unique_id = f"{device_id}_actively_heating"

    @property
    def is_on(self) -> bool:
        """Return true if actively heating.

        Heater states from device firmware research:
        - 0: Off
        - 2: Reduced power (heating)
        - 3: Full power (heating)
        - 4: Idle at target temperature
        - 5: Reduced power post-target (heating)
        - 6: Full power post-target (heating)

        States 2,3,5,6 indicate active heating.
        State 4 is idle (at target, no heating).
        """
        heater_state = self.coordinator.data.get("heater_state", 0)
        power_state = self.coordinator.data.get("power_state", 0)

        # Only heating if power is on and heater in active state
        if power_state != 1:
            return False

        return heater_state in [2, 3, 5, 6]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return heating details as attributes."""
        heater_state = self.coordinator.data.get("heater_state", 0)

        # Map heater state to human-readable status
        status_map = {
            0: "off",
            2: "reduced_power",
            3: "full_power",
            4: "idle_at_target",
            5: "reduced_power_maintaining",
            6: "full_power_maintaining",
        }

        return {
            "heater_state": heater_state,
            "heating_mode": status_map.get(heater_state, f"unknown_{heater_state}"),
        }
