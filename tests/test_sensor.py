"""Test sensor entities."""

import pytest
from datetime import date
from homeassistant.const import UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.new_bestway_spa.sensor import BestwaySpaSensor, DaysSinceSensor
from custom_components.new_bestway_spa.const import DOMAIN


pytestmark = pytest.mark.asyncio




async def test_temperature_sensor_fahrenheit(hass: HomeAssistant, mock_coordinator):
    """Test temperature sensor uses Fahrenheit when unit is 0."""
    mock_coordinator.data["water_temperature"] = 98
    mock_coordinator.data["temperature_unit"] = 0

    sensor = BestwaySpaSensor(
        mock_coordinator,
        "water_temperature",
        "Water Temperature",
        "Test Spa",
        "test_spa",
    )

    assert sensor.native_value == 98
    assert sensor.native_unit_of_measurement == UnitOfTemperature.FAHRENHEIT












async def test_days_since_filter_calculation(hass: HomeAssistant, mock_coordinator):
    """Test days since filter calculates correctly."""
    # Create mock config entry with filter date 7 days ago
    past_date = (date.today() - date.resolution * 7).strftime("%Y-%m-%d")

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Spa",
        data={"filter_last_change": past_date},
    )

    sensor = DaysSinceSensor(
        mock_coordinator, config_entry, "Filter", "filter_last_change", "test_spa"
    )

    assert sensor.native_value == 7
    assert sensor.native_unit_of_measurement == UnitOfTime.DAYS


async def test_days_since_chlorine_calculation(hass: HomeAssistant, mock_coordinator):
    """Test days since chlorine calculates correctly."""
    # Create mock config entry with chlorine date today
    today = date.today().strftime("%Y-%m-%d")

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Spa",
        data={"chlorine_last_add": today},
    )

    sensor = DaysSinceSensor(
        mock_coordinator, config_entry, "Chlorine", "chlorine_last_add", "test_spa"
    )

    assert sensor.native_value == 0


async def test_days_since_sensor_no_date(hass: HomeAssistant, mock_coordinator):
    """Test days since sensor returns None when no date stored."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Spa",
        data={},
    )

    sensor = DaysSinceSensor(
        mock_coordinator, config_entry, "Filter", "filter_last_change", "test_spa"
    )

    assert sensor.native_value is None


async def test_days_since_sensor_invalid_date(hass: HomeAssistant, mock_coordinator):
    """Test days since sensor returns None for invalid date format."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Spa",
        data={"filter_last_change": "invalid-date"},
    )

    sensor = DaysSinceSensor(
        mock_coordinator, config_entry, "Filter", "filter_last_change", "test_spa"
    )

    assert sensor.native_value is None


