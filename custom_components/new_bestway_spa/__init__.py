from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .coordinator import BestwayUpdateCoordinator
from .spa_api import BestwaySpaAPI, authenticate
from .websocket import BestwayWebSocket

_LOGGER = logging.getLogger(__name__)

_PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


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

    # Determine polling interval based on WebSocket availability
    # If service_region available: use WebSocket with 5-min polling backup
    # If no service_region: use 60s polling (backward compatibility)
    has_websocket = "service_region" in entry.data
    update_interval = timedelta(minutes=5) if has_websocket else timedelta(seconds=60)

    coordinator = BestwayUpdateCoordinator(
        hass, entry, api, entry.data["device_id"], update_interval
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
        _LOGGER.info(
            "Starting WebSocket for real-time updates (region: %s)",
            entry.data.get("service_region"),
        )

        try:
            websocket = BestwayWebSocket(
                device_id=entry.data["device_id"],
                service_region=entry.data["service_region"],
                token=token,
                callback=coordinator.handle_websocket_update,
                token_refresh_callback=refresh_token,
            )

            # Start WebSocket connection in background
            hass.async_create_task(websocket.connect())

            # Store WebSocket instance for cleanup
            hass.data[DOMAIN][entry.entry_id]["websocket"] = websocket

            _LOGGER.info("✓ WebSocket configured (polling reduced to 5 minutes)")

        except Exception as e:
            _LOGGER.error(
                "Failed to start WebSocket: %s (falling back to polling only)", str(e)
            )
            websocket = None

    else:
        _LOGGER.info("No service_region available, using polling only (60s interval)")

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    # Clean up WebSocket connection if it exists
    if entry.entry_id in hass.data.get(DOMAIN, {}):
        websocket = hass.data[DOMAIN][entry.entry_id].get("websocket")
        if websocket:
            _LOGGER.info(
                "Disconnecting WebSocket for device %s",
                entry.data.get("device_id", "unknown")[:20],
            )
            try:
                await websocket.disconnect()
            except Exception as e:
                _LOGGER.error("Error disconnecting WebSocket: %s", str(e))

    # Unload platforms
    unload_ok: bool = await hass.config_entries.async_unload_platforms(
        entry, _PLATFORMS
    )

    if unload_ok:
        # Clean up entry data (session is shared, no need to close)
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
