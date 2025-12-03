"""Test coordinator data management and WebSocket handling."""

import pytest
from unittest.mock import AsyncMock
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.new_bestway_spa.coordinator import BestwayUpdateCoordinator


pytestmark = pytest.mark.asyncio


async def test_coordinator_fetch_data_success(hass: HomeAssistant, mock_api):
    """Test coordinator successfully fetches data from API."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    from custom_components.new_bestway_spa.const import DOMAIN

    mock_entry = MockConfigEntry(domain=DOMAIN, data={"device_id": "test_device_123"})

    from pytest_homeassistant_custom_component.common import MockConfigEntry
    from custom_components.new_bestway_spa.const import DOMAIN

    mock_entry = MockConfigEntry(domain=DOMAIN, data={"device_id": "test_device_123"})

    coordinator = BestwayUpdateCoordinator(
        hass=hass,
        config_entry=mock_entry,
        api=mock_api,
        device_id="test_device_123",
        update_interval=timedelta(seconds=60),
    )

    # Trigger refresh
    await coordinator.async_refresh()

    # Verify data fetched
    assert coordinator.data is not None
    assert coordinator.data["power_state"] == 1
    assert coordinator.data["heater_state"] == 0
    assert coordinator.data["water_temperature"] == 22
    assert coordinator.data["is_online"] is True

    # Verify API was called
    mock_api.get_status.assert_called_once()


async def test_coordinator_fetch_data_failure(hass: HomeAssistant, mock_api):
    """Test coordinator handles API fetch failures."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    from custom_components.new_bestway_spa.const import DOMAIN

    mock_entry = MockConfigEntry(domain=DOMAIN, data={"device_id": "test_device_123"})

    from pytest_homeassistant_custom_component.common import MockConfigEntry
    from custom_components.new_bestway_spa.const import DOMAIN

    mock_entry = MockConfigEntry(domain=DOMAIN, data={"device_id": "test_device_123"})

    coordinator = BestwayUpdateCoordinator(
        hass=hass,
        config_entry=mock_entry,
        api=mock_api,
        device_id="test_device_123",
        update_interval=timedelta(seconds=60),
    )

    # Mock API to raise exception
    mock_api.get_status = AsyncMock(side_effect=Exception("Connection timeout"))

    # Call _async_update_data directly to get the exception
    with pytest.raises(UpdateFailed) as exc_info:
        await coordinator._async_update_data()

    # Verify error message
    assert "Error fetching spa data" in str(exc_info.value)


async def test_websocket_delta_merge(hass: HomeAssistant, mock_api):
    """Test WebSocket delta updates merge with existing data."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    from custom_components.new_bestway_spa.const import DOMAIN

    mock_entry = MockConfigEntry(domain=DOMAIN, data={"device_id": "test_device_123"})

    from pytest_homeassistant_custom_component.common import MockConfigEntry
    from custom_components.new_bestway_spa.const import DOMAIN

    mock_entry = MockConfigEntry(domain=DOMAIN, data={"device_id": "test_device_123"})

    coordinator = BestwayUpdateCoordinator(
        hass=hass,
        config_entry=mock_entry,
        api=mock_api,
        device_id="test_device_123",
        update_interval=timedelta(seconds=60),
    )

    # Set initial data
    coordinator.data = {
        "power_state": 1,
        "heater_state": 0,
        "water_temperature": 22,
        "temperature_setting": 28,
        "is_online": True,
    }

    # Send delta update (only heater_state changed)
    coordinator.handle_websocket_update({"heater_state": 3})

    # Verify data merged correctly
    assert coordinator.data["power_state"] == 1  # Preserved
    assert coordinator.data["heater_state"] == 3  # Updated
    assert coordinator.data["water_temperature"] == 22  # Preserved
    assert coordinator.data["temperature_setting"] == 28  # Preserved
    assert coordinator.data["is_online"] is True  # Preserved


async def test_websocket_multiple_fields_update(hass: HomeAssistant, mock_api):
    """Test WebSocket can update multiple fields at once."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    from custom_components.new_bestway_spa.const import DOMAIN

    mock_entry = MockConfigEntry(domain=DOMAIN, data={"device_id": "test_device_123"})

    from pytest_homeassistant_custom_component.common import MockConfigEntry
    from custom_components.new_bestway_spa.const import DOMAIN

    mock_entry = MockConfigEntry(domain=DOMAIN, data={"device_id": "test_device_123"})

    coordinator = BestwayUpdateCoordinator(
        hass=hass,
        config_entry=mock_entry,
        api=mock_api,
        device_id="test_device_123",
        update_interval=timedelta(seconds=60),
    )

    # Set initial data
    coordinator.data = {
        "power_state": 1,
        "heater_state": 0,
        "filter_state": 0,
        "water_temperature": 22,
    }

    # Send delta with multiple changes
    coordinator.handle_websocket_update(
        {"heater_state": 3, "filter_state": 1, "water_temperature": 23}
    )

    # Verify all fields updated
    assert coordinator.data["power_state"] == 1  # Preserved
    assert coordinator.data["heater_state"] == 3  # Updated
    assert coordinator.data["filter_state"] == 1  # Updated
    assert coordinator.data["water_temperature"] == 23  # Updated


async def test_websocket_internal_field_filtering(hass: HomeAssistant, mock_api):
    """Test WebSocket ignores internal firmware fields (B/P fields)."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    from custom_components.new_bestway_spa.const import DOMAIN

    mock_entry = MockConfigEntry(domain=DOMAIN, data={"device_id": "test_device_123"})

    from pytest_homeassistant_custom_component.common import MockConfigEntry
    from custom_components.new_bestway_spa.const import DOMAIN

    mock_entry = MockConfigEntry(domain=DOMAIN, data={"device_id": "test_device_123"})

    coordinator = BestwayUpdateCoordinator(
        hass=hass,
        config_entry=mock_entry,
        api=mock_api,
        device_id="test_device_123",
        update_interval=timedelta(seconds=60),
    )

    # Set initial data
    coordinator.data = {
        "power_state": 1,
        "heater_state": 0,
    }
    initial_data = coordinator.data.copy()

    # Send update with ONLY internal fields
    coordinator.handle_websocket_update(
        {
            "B0": 1,
            "B3": 123,
            "B7": 456,
            "P0": 789,
            "P2": 999,
            "local_timestamp": "2024-12-03T10:30:00Z",
        }
    )

    # Verify data unchanged (internal fields ignored)
    assert coordinator.data == initial_data
    assert "B0" not in coordinator.data
    assert "P0" not in coordinator.data
    assert "local_timestamp" not in coordinator.data


async def test_websocket_mixed_fields_update(hass: HomeAssistant, mock_api):
    """Test WebSocket processes user-facing fields while ignoring internal ones."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    from custom_components.new_bestway_spa.const import DOMAIN

    mock_entry = MockConfigEntry(domain=DOMAIN, data={"device_id": "test_device_123"})

    from pytest_homeassistant_custom_component.common import MockConfigEntry
    from custom_components.new_bestway_spa.const import DOMAIN

    mock_entry = MockConfigEntry(domain=DOMAIN, data={"device_id": "test_device_123"})

    coordinator = BestwayUpdateCoordinator(
        hass=hass,
        config_entry=mock_entry,
        api=mock_api,
        device_id="test_device_123",
        update_interval=timedelta(seconds=60),
    )

    # Set initial data
    coordinator.data = {
        "power_state": 1,
        "heater_state": 0,
    }

    # Send update with mixed fields
    coordinator.handle_websocket_update(
        {
            "heater_state": 3,  # User-facing
            "B3": 123,  # Internal (should be ignored)
            "P0": 456,  # Internal (should be ignored)
            "water_temperature": 24,  # User-facing
        }
    )

    # Verify only user-facing fields updated
    assert coordinator.data["power_state"] == 1  # Preserved
    assert coordinator.data["heater_state"] == 3  # Updated
    assert coordinator.data["water_temperature"] == 24  # Updated
    assert "B3" not in coordinator.data  # Ignored
    assert "P0" not in coordinator.data  # Ignored






async def test_websocket_type_normalization_both_fields(hass: HomeAssistant, mock_api):
    """Test WebSocket normalizes both warning and error_code together."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    from custom_components.new_bestway_spa.const import DOMAIN

    mock_entry = MockConfigEntry(domain=DOMAIN, data={"device_id": "test_device_123"})

    from pytest_homeassistant_custom_component.common import MockConfigEntry
    from custom_components.new_bestway_spa.const import DOMAIN

    mock_entry = MockConfigEntry(domain=DOMAIN, data={"device_id": "test_device_123"})

    coordinator = BestwayUpdateCoordinator(
        hass=hass,
        config_entry=mock_entry,
        api=mock_api,
        device_id="test_device_123",
        update_interval=timedelta(seconds=60),
    )

    # Set initial data
    coordinator.data = {"power_state": 1, "warning": 5, "error_code": 3}

    # Send update with empty strings for both
    coordinator.handle_websocket_update({"warning": "", "error_code": ""})

    # Verify both normalized to 0
    assert coordinator.data["warning"] == 0
    assert coordinator.data["error_code"] == 0
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    from custom_components.new_bestway_spa.const import DOMAIN

    mock_entry = MockConfigEntry(domain=DOMAIN, data={"device_id": "test_device_123"})


async def test_websocket_preserves_non_empty_warning_error(
    hass: HomeAssistant, mock_api
):
    """Test WebSocket preserves non-empty warning/error_code values."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    from custom_components.new_bestway_spa.const import DOMAIN

    mock_entry = MockConfigEntry(domain=DOMAIN, data={"device_id": "test_device_123"})

    coordinator = BestwayUpdateCoordinator(
        hass=hass,
        config_entry=mock_entry,
        api=mock_api,
        device_id="test_device_123",
        update_interval=timedelta(seconds=60),
    )

    # Set initial data
    coordinator.data = {"power_state": 1, "warning": 0, "error_code": 0}

    # Send update with actual values
    coordinator.handle_websocket_update({"warning": 5, "error_code": 3})

    # Verify values preserved
    assert coordinator.data["warning"] == 5
    assert coordinator.data["error_code"] == 3


async def test_websocket_field_name_normalization(hass: HomeAssistant, mock_api):
    """Test WebSocket normalizes field names to match get_status() format."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    from custom_components.new_bestway_spa.const import DOMAIN

    mock_entry = MockConfigEntry(domain=DOMAIN, data={"device_id": "test_device_123"})

    from pytest_homeassistant_custom_component.common import MockConfigEntry
    from custom_components.new_bestway_spa.const import DOMAIN

    mock_entry = MockConfigEntry(domain=DOMAIN, data={"device_id": "test_device_123"})

    coordinator = BestwayUpdateCoordinator(
        hass=hass,
        config_entry=mock_entry,
        api=mock_api,
        device_id="test_device_123",
        update_interval=timedelta(seconds=60),
    )

    # Set initial data
    coordinator.data = {"power_state": 1}

    # Send update with WebSocket field names (not normalized)
    coordinator.handle_websocket_update(
        {
            "wifivertion": "1.2.3",
            "mcuversion": "4.5.6",
            "otastatus": "idle",
            "ConnectType": "wifi",
        }
    )

    # Verify field names normalized
    assert coordinator.data["wifi_version"] == "1.2.3"
    assert coordinator.data["mcu_version"] == "4.5.6"
    assert coordinator.data["ota_status"] == "idle"
    assert coordinator.data["connect_type"] == "wifi"

    # Verify original names not in data
    assert "wifivertion" not in coordinator.data
    assert "mcuversion" not in coordinator.data
    assert "ConnectType" not in coordinator.data


async def test_websocket_empty_initial_data(hass: HomeAssistant, mock_api):
    """Test WebSocket handles update when coordinator has no initial data."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    from custom_components.new_bestway_spa.const import DOMAIN

    mock_entry = MockConfigEntry(domain=DOMAIN, data={"device_id": "test_device_123"})

    from pytest_homeassistant_custom_component.common import MockConfigEntry
    from custom_components.new_bestway_spa.const import DOMAIN

    mock_entry = MockConfigEntry(domain=DOMAIN, data={"device_id": "test_device_123"})

    coordinator = BestwayUpdateCoordinator(
        hass=hass,
        config_entry=mock_entry,
        api=mock_api,
        device_id="test_device_123",
        update_interval=timedelta(seconds=60),
    )

    # No initial data
    coordinator.data = None

    # Send update
    coordinator.handle_websocket_update({"power_state": 1, "heater_state": 3})

    # Verify data created
    assert coordinator.data is not None
    assert coordinator.data["power_state"] == 1
    assert coordinator.data["heater_state"] == 3
