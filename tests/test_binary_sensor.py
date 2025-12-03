"""Test binary sensor entities."""

import pytest
from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory

from custom_components.new_bestway_spa.binary_sensor import (
    BestwayConnectivitySensor,
    BestwayErrorSensor,
    BestwayActivelyHeatingSensor,
)


pytestmark = pytest.mark.asyncio








async def test_error_sensor_with_error_code(hass: HomeAssistant, mock_coordinator):
    """Test error sensor reports on when error_code is non-zero."""
    mock_coordinator.data["error_code"] = 3
    mock_coordinator.data["warning"] = 0

    sensor = BestwayErrorSensor(mock_coordinator, "test_spa", "Test Spa")

    assert sensor.is_on is True

    # Check attributes
    attrs = sensor.extra_state_attributes
    assert attrs["error_code"] == 3
    assert attrs["status"] == "Error: E03"


async def test_error_sensor_with_warning(hass: HomeAssistant, mock_coordinator):
    """Test error sensor reports on when warning is non-zero."""
    mock_coordinator.data["error_code"] = 0
    mock_coordinator.data["warning"] = 5

    sensor = BestwayErrorSensor(mock_coordinator, "test_spa", "Test Spa")

    assert sensor.is_on is True

    # Check attributes
    attrs = sensor.extra_state_attributes
    assert attrs["warning"] == 5
    assert attrs["status"] == "Warning: 5"




async def test_actively_heating_sensor_heating_states(
    hass: HomeAssistant, mock_coordinator
):
    """Test heating sensor reports on for actively heating states (2,3,5,6)."""
    mock_coordinator.data["power_state"] = 1

    sensor = BestwayActivelyHeatingSensor(mock_coordinator, "test_spa", "Test Spa")

    # Test all actively heating states
    for state in [2, 3, 5, 6]:
        mock_coordinator.data["heater_state"] = state
        assert sensor.is_on is True, f"State {state} should report heating"


async def test_actively_heating_sensor_idle_state(
    hass: HomeAssistant, mock_coordinator
):
    """Test heating sensor reports off for idle state (4)."""
    mock_coordinator.data["power_state"] = 1
    mock_coordinator.data["heater_state"] = 4

    sensor = BestwayActivelyHeatingSensor(mock_coordinator, "test_spa", "Test Spa")

    assert sensor.is_on is False

    # Check attributes
    attrs = sensor.extra_state_attributes
    assert attrs["heater_state"] == 4
    assert attrs["heating_mode"] == "idle_at_target"








