"""Test switch entities."""

import pytest
from unittest.mock import AsyncMock
from homeassistant.core import HomeAssistant

from custom_components.new_bestway_spa.switch import BestwaySpaSwitch
from custom_components.new_bestway_spa.const import Icon


pytestmark = pytest.mark.asyncio










async def test_heater_switch_on_states(hass: HomeAssistant, mock_coordinator, mock_api):
    """Test heater switch reports on for any non-zero state."""
    switch = BestwaySpaSwitch(
        mock_coordinator, mock_api, "heater_state", "Spa Heater", Icon.HEATER, "Test Spa", "test_spa"
    )

    # Test all heater states
    for state in [2, 3, 4, 5, 6]:
        mock_coordinator.data["heater_state"] = state
        assert switch.is_on is True, f"State {state} should report on"














async def test_switch_turn_on(hass: HomeAssistant, mock_coordinator, mock_api):
    """Test turning switch on calls API."""
    switch = BestwaySpaSwitch(
        mock_coordinator, mock_api, "power_state", "Power", Icon.POWER, "Test Spa", "test_spa"
    )

    mock_coordinator.async_request_refresh = AsyncMock()

    await switch.async_turn_on()

    # Verify API called
    mock_api.set_state.assert_called_once_with("power_state", 1)

    # Verify refresh requested
    mock_coordinator.async_request_refresh.assert_called_once()


async def test_switch_turn_off(hass: HomeAssistant, mock_coordinator, mock_api):
    """Test turning switch off calls API."""
    switch = BestwaySpaSwitch(
        mock_coordinator, mock_api, "power_state", "Power", Icon.POWER, "Test Spa", "test_spa"
    )

    mock_coordinator.async_request_refresh = AsyncMock()

    await switch.async_turn_off()

    # Verify API called
    mock_api.set_state.assert_called_once_with("power_state", 0)

    # Verify refresh requested
    mock_coordinator.async_request_refresh.assert_called_once()
