"""Base entity for Bestway Spa integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN


class BestwayEntity(CoordinatorEntity[DataUpdateCoordinator]):
    """Base class for all Bestway Spa entities."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device_id: str,
        device_name: str,
        product_id: str | None = None,
        product_series: str | None = None,
    ) -> None:
        """Initialize the entity.

        Args:
            coordinator: Data update coordinator
            device_id: Unique device identifier
            device_name: Human-readable device name
            product_id: Product model identifier (e.g., "T53NN8")
            product_series: Product series name (e.g., "AIRJET", "HYDROJET")
        """
        super().__init__(coordinator)
        self._device_id = device_id
        self._device_name = device_name
        self._product_id = product_id
        self._product_series = product_series

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for this entity.

        Returns device registry information that groups all entities
        for this device together in the UI.
        """
        # Build model string: "AIRJET (T53NN8)" or just "T53NN8" if no series
        if self._product_series and self._product_id:
            model = f"{self._product_series} ({self._product_id})"
        elif self._product_id:
            model = self._product_id
        elif self._product_series:
            model = self._product_series
        else:
            model = "Smart Spa"

        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=self._device_name,
            manufacturer="Bestway",
            model=model,
            sw_version=self.coordinator.data.get("mcu_version", "Unknown"),
        )

    @property
    def available(self) -> bool:
        """Return if entity is available.

        Entity is available if:
        - Coordinator successfully fetched data recently
        - Device is reporting as online
        """
        return self.coordinator.last_update_success and self.coordinator.data.get(
            "is_online", False
        )
