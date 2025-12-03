"""Test climate entity."""

import pytest
from unittest.mock import AsyncMock
from homeassistant.components.climate.const import HVACMode, HVACAction
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant

from custom_components.new_bestway_spa.climate import BestwaySpaThermostat


pytestmark = pytest.mark.asyncio










async def test_climate_temperature_unit_fahrenheit(
    hass: HomeAssistant, mock_coordinator, mock_api
):
    """Test climate entity uses Fahrenheit when unit is 0."""
    mock_coordinator.data["temperature_unit"] = 0

    climate = BestwaySpaThermostat(
        mock_coordinator, mock_api, "Test Spa", "test_spa", hass
    )

    assert climate.temperature_unit == UnitOfTemperature.FAHRENHEIT
    assert climate.min_temp == 68
    assert climate.max_temp == 104










async def test_climate_hvac_action_heating(
    hass: HomeAssistant, mock_coordinator, mock_api
):
    """Test HVAC action is HEATING for states 2,3,5,6."""
    mock_coordinator.data["power_state"] = 1

    climate = BestwaySpaThermostat(
        mock_coordinator, mock_api, "Test Spa", "test_spa", hass
    )

    # Test all actively heating states
    for state in [2, 3, 5, 6]:
        mock_coordinator.data["heater_state"] = state
        assert (
            climate.hvac_action == HVACAction.HEATING
        ), f"State {state} should be HEATING"




async def test_climate_set_temperature(hass: HomeAssistant, mock_coordinator, mock_api):
    """Test setting target temperature calls API."""
    climate = BestwaySpaThermostat(
        mock_coordinator, mock_api, "Test Spa", "test_spa", hass
    )

    # Mock async_request_refresh
    mock_coordinator.async_request_refresh = AsyncMock()

    await climate.async_set_temperature(temperature=35)

    # Verify API was called with integer value
    mock_api.set_state.assert_called_once_with("temperature_setting", 35)

    # Verify coordinator refresh was requested
    mock_coordinator.async_request_refresh.assert_called_once()


async def test_climate_set_hvac_mode_heat(
    hass: HomeAssistant, mock_coordinator, mock_api
):
    """Test setting HVAC mode to HEAT."""
    climate = BestwaySpaThermostat(
        mock_coordinator, mock_api, "Test Spa", "test_spa", hass
    )

    mock_coordinator.async_request_refresh = AsyncMock()

    await climate.async_set_hvac_mode(HVACMode.HEAT)

    # Verify heater turned on
    mock_api.set_state.assert_called_with("heater_state", 1)


async def test_climate_set_hvac_mode_off(
    hass: HomeAssistant, mock_coordinator, mock_api
):
    """Test setting HVAC mode to OFF."""
    climate = BestwaySpaThermostat(
        mock_coordinator, mock_api, "Test Spa", "test_spa", hass
    )

    mock_coordinator.async_request_refresh = AsyncMock()

    await climate.async_set_hvac_mode(HVACMode.OFF)

    # Verify heater turned off
    mock_api.set_state.assert_called_with("heater_state", 0)

    # Verify coordinator refresh was requested
    mock_coordinator.async_request_refresh.assert_called_once()




