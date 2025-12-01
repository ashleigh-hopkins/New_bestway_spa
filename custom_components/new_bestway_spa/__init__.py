from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from datetime import timedelta
from .const import DOMAIN
from .spa_api import BestwaySpaAPI, authenticate
from .websocket import BestwayWebSocket
import logging

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["switch", "number", "sensor", "climate", "select", "button"]
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Bestway Spa from a config entry."""

    # Use Home Assistant's shared session (best practice)
    session = async_get_clientsession(hass)

    # Initial authentication
    token = await authenticate(session, entry.data)
    if not token:
        _LOGGER.error("Authentication failed: No token returned")
        return False

    # Token refresh callback for when token expires
    async def refresh_token():
        """Get fresh token when current one expires."""
        _LOGGER.info("Refreshing authentication token...")
        new_token = await authenticate(session, entry.data)
        if new_token:
            # Update API instance
            api.token = new_token
            _LOGGER.info("✓ Token refreshed successfully")
            return new_token
        else:
            _LOGGER.error("Failed to refresh token")
            return None

    api = BestwaySpaAPI(session, {**entry.data, "token": token})

    async def async_update_data():
        try:
            return await api.get_status()
        except Exception as err:
            raise UpdateFailed(f"Error fetching spa data: {err}") from err

    # Determine polling interval based on WebSocket availability
    # If service_region available: use WebSocket with 5-min polling backup
    # If no service_region: use 60s polling (backward compatibility)
    has_websocket = "service_region" in entry.data
    update_interval = timedelta(minutes=5) if has_websocket else timedelta(seconds=60)

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="Bestway Spa",
        update_method=async_update_data,
        update_interval=update_interval,
    )

    await coordinator.async_config_entry_first_refresh()

    if not coordinator.last_update_success:
        return False

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "coordinator": coordinator,
    }

    # Start WebSocket for real-time updates if service_region available
    websocket = None
    if has_websocket:
        _LOGGER.info("Starting WebSocket for real-time updates (region: %s)",
                    entry.data.get("service_region"))

        def state_callback(state: dict):
            """Handle WebSocket state update.

            WebSocket sends delta updates (only changed fields), so we must merge
            with existing coordinator data to preserve all fields.

            Filters out internal firmware fields (B0-B10, P0-P2, local_*) that
            update every 1-2 seconds and cause unnecessary UI refreshes.
            """
            # Filter: Only process user-facing fields, ignore internal firmware telemetry
            user_facing_fields = {
                "wifivertion", "otastatus", "mcuversion", "trdversion", "ConnectType",
                "power_state", "heater_state", "wave_state", "filter_state",
                "temperature_setting", "temperature_unit", "water_temperature",
                "warning", "error_code", "hydrojet_state", "is_online"
            }

            # Check if any user-facing field changed
            has_meaningful_change = any(key in user_facing_fields for key in state.keys())

            if not has_meaningful_change:
                # Only internal fields changed (B0-B10, P0-P2), skip update
                _LOGGER.debug("WebSocket update ignored: only internal firmware fields changed")
                return

            # Normalize WebSocket field names to match get_status() format
            normalized = {}

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
                normalized["error_code"] = 0 if state["error_code"] == "" else state["error_code"]
            if "hydrojet_state" in state:
                normalized["hydrojet_state"] = state["hydrojet_state"]
            if "is_online" in state:
                normalized["is_online"] = state["is_online"]

            # Merge with existing coordinator data (WebSocket sends deltas, not full state)
            if coordinator.data:
                merged = {**coordinator.data, **normalized}
            else:
                merged = normalized

            _LOGGER.debug("WebSocket delta update: %d user-facing fields changed", len(normalized))
            coordinator.async_set_updated_data(merged)

        try:
            websocket = BestwayWebSocket(
                device_id=entry.data["device_id"],
                service_region=entry.data["service_region"],
                token=token,  # Fresh token from line 21
                callback=state_callback,
                token_refresh_callback=refresh_token
            )

            # Start WebSocket connection in background
            hass.async_create_task(websocket.connect())

            # Store WebSocket instance for cleanup
            hass.data[DOMAIN][entry.entry_id]["websocket"] = websocket

            _LOGGER.info("✓ WebSocket configured (polling reduced to 5 minutes)")

        except Exception as e:
            _LOGGER.error("Failed to start WebSocket: %s (falling back to polling only)", str(e))
            websocket = None

    else:
        _LOGGER.info("No service_region available, using polling only (60s interval)")

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    # Clean up WebSocket connection if it exists
    websocket = hass.data[DOMAIN][entry.entry_id].get("websocket")
    if websocket:
        _LOGGER.info("Disconnecting WebSocket for device %s",
                    entry.data.get("device_id", "unknown")[:20])
        try:
            await websocket.disconnect()
        except Exception as e:
            _LOGGER.error("Error disconnecting WebSocket: %s", str(e))

    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        # Clean up entry data (session is shared, no need to close)
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
