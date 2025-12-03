"""Data update coordinator for Bestway Spa integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .spa_api import BestwaySpaAPI

_LOGGER = logging.getLogger(__name__)


class BestwayUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to manage fetching Bestway spa data."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        api: BestwaySpaAPI,
        device_id: str,
        update_interval: timedelta,
    ) -> None:
        """Initialize coordinator.

        Args:
            hass: Home Assistant instance
            config_entry: Config entry for this integration
            api: Bestway Spa API client
            device_id: Device identifier
            update_interval: How often to poll for updates
        """
        super().__init__(
            hass,
            _LOGGER,
            name="Bestway Spa",
            config_entry=config_entry,
            update_interval=update_interval,
        )
        self.api = api
        self.device_id = device_id

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from API.

        Returns:
            Device state dictionary

        Raises:
            UpdateFailed: If unable to fetch data
        """
        try:
            return await self.api.get_status()
        except Exception as err:
            raise UpdateFailed(f"Error fetching spa data: {err}") from err

    def handle_websocket_update(self, state: dict) -> None:
        """Handle WebSocket state delta update.

        WebSocket sends delta updates (only changed fields), so we must merge
        with existing coordinator data to preserve all fields.

        Filters out internal firmware fields (B0-B10, P0-P2, local_*) that
        update every 1-2 seconds and cause unnecessary UI refreshes.

        Args:
            state: Delta state update from WebSocket
        """
        # Filter: Only process user-facing fields, ignore internal firmware telemetry
        user_facing_fields = {
            "wifivertion",
            "otastatus",
            "mcuversion",
            "trdversion",
            "ConnectType",
            "power_state",
            "heater_state",
            "wave_state",
            "filter_state",
            "temperature_setting",
            "temperature_unit",
            "water_temperature",
            "warning",
            "error_code",
            "hydrojet_state",
            "is_online",
        }

        # Check if any user-facing field changed
        has_meaningful_change = any(key in user_facing_fields for key in state.keys())

        if not has_meaningful_change:
            # Only internal fields changed (B0-B10, P0-P2), skip update
            _LOGGER.debug(
                "WebSocket update ignored: only internal firmware fields changed"
            )
            return

        # Normalize WebSocket field names to match get_status() format
        normalized: dict[str, Any] = {}

        if "wifivertion" in state:
            normalized["wifi_version"] = state["wifivertion"]
        if "otastatus" in state:
            normalized["ota_status"] = state["otastatus"]
        if "mcuversion" in state:
            normalized["mcu_version"] = state["mcuversion"]
        if "trdversion" in state:
            normalized["trd_version"] = state["trdversion"]
        if "ConnectType" in state:
            normalized["connect_type"] = state["ConnectType"]
        if "power_state" in state:
            normalized["power_state"] = state["power_state"]
        if "heater_state" in state:
            normalized["heater_state"] = state["heater_state"]
        if "wave_state" in state:
            normalized["wave_state"] = state["wave_state"]
        if "filter_state" in state:
            normalized["filter_state"] = state["filter_state"]
        if "temperature_setting" in state:
            normalized["temperature_setting"] = state["temperature_setting"]
        if "temperature_unit" in state:
            normalized["temperature_unit"] = state["temperature_unit"]
        if "water_temperature" in state:
            normalized["water_temperature"] = state["water_temperature"]
        if "warning" in state:
            # Normalize empty string to 0 for consistency
            normalized["warning"] = 0 if state["warning"] == "" else state["warning"]
        if "error_code" in state:
            # Normalize empty string to 0 for consistency
            normalized["error_code"] = (
                0 if state["error_code"] == "" else state["error_code"]
            )
        if "hydrojet_state" in state:
            normalized["hydrojet_state"] = state["hydrojet_state"]
        if "is_online" in state:
            normalized["is_online"] = state["is_online"]

        # Merge with existing coordinator data (WebSocket sends deltas, not full state)
        if self.data:
            merged = {**self.data, **normalized}
        else:
            merged = normalized

        _LOGGER.debug(
            "WebSocket delta update: %d user-facing fields changed", len(normalized)
        )
        self.async_set_updated_data(merged)
