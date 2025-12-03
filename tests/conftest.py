"""Fixtures for Bestway Spa integration tests."""

import pytest
from unittest.mock import patch, AsyncMock

pytest_plugins = "pytest_homeassistant_custom_component"


# Enable loading custom integrations
@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable loading custom integrations."""
    yield


# Skip notification calls
@pytest.fixture(name="skip_notifications", autouse=True)
def skip_notifications_fixture():
    """Skip notification calls."""
    with (
        patch("homeassistant.components.persistent_notification.async_create"),
        patch("homeassistant.components.persistent_notification.async_dismiss"),
    ):
        yield


# Bypass authentication
@pytest.fixture(name="bypass_auth")
def bypass_auth():
    """Skip authentication."""
    with patch("custom_components.new_bestway_spa.authenticate") as mock:
        mock.return_value = "test_token_123456"
        yield


# Bypass get_status calls
@pytest.fixture(name="bypass_get_data")
def bypass_get_data_fixture():
    """Skip calls to get data from API."""
    with patch(
        "custom_components.new_bestway_spa.spa_api.BestwaySpaAPI.get_status"
    ) as mock:
        mock.return_value = {
            "power_state": 1,
            "heater_state": 0,
            "filter_state": 0,
            "wave_state": 0,
            "water_temperature": 22,
            "temperature_setting": 28,
            "temperature_unit": 1,
            "is_online": True,
            "error_code": 0,
            "warning": 0,
        }
        yield


# Error on get_status
@pytest.fixture(name="error_on_get_data")
def error_get_data_fixture():
    """Simulate error when retrieving data from API."""
    with patch(
        "custom_components.new_bestway_spa.spa_api.BestwaySpaAPI.get_status",
        side_effect=Exception("API Error"),
    ):
        yield


@pytest.fixture
def mock_api():
    """Mock BestwaySpaAPI for testing."""
    with patch("custom_components.new_bestway_spa.spa_api.BestwaySpaAPI") as mock:
        api_instance = mock.return_value

        # Mock get_status response (from real device)
        api_instance.get_status = AsyncMock(
            return_value={
                "power_state": 1,
                "heater_state": 0,
                "filter_state": 0,
                "wave_state": 0,
                "water_temperature": 22,
                "temperature_setting": 28,
                "temperature_unit": 1,
                "is_online": True,
                "error_code": 0,
                "warning": 0,
            }
        )

        # Mock set_state response
        api_instance.set_state = AsyncMock(
            return_value={"code": 0, "message": "SUCCESS"}
        )

        # Mock discover_devices response (test data, no real device IDs)
        api_instance.discover_devices = AsyncMock(
            return_value=[
                {
                    "device_id": "test_device_123abc",
                    "device_alias": "Test Spa",
                    "product_id": "T53NN8",
                    "service_region": "eu-central-1",
                    "is_online": True,
                }
            ]
        )

        # Mock get_device_info
        api_instance.get_device_info = AsyncMock(
            return_value={
                "device_id": "test_device_123abc",
                "device_alias": "Test Spa",
                "product_id": "T53NN8",
                "service_region": "eu-central-1",
                "is_online": True,
            }
        )

        # Mock bind_device_qr (success case)
        api_instance.bind_device_qr = AsyncMock(
            return_value={
                "device_id": "test_device_123abc",
                "name": "Test Spa",
                "binding_role": 3,
            }
        )

        yield api_instance


@pytest.fixture
def mock_websocket():
    """Mock BestwayWebSocket for testing."""
    with patch("custom_components.new_bestway_spa.websocket.BestwayWebSocket") as mock:
        ws_instance = mock.return_value

        ws_instance.connect = AsyncMock()
        ws_instance.disconnect = AsyncMock()
        ws_instance._running = False

        yield ws_instance


@pytest.fixture
def mock_authenticate():
    """Mock authenticate function."""
    with patch("custom_components.new_bestway_spa.spa_api.authenticate") as mock:
        mock.return_value = "test_token_123456"
        yield mock


@pytest.fixture
async def mock_coordinator(hass, mock_api):
    """Create a mock coordinator with test data for entity testing."""
    from datetime import timedelta
    from custom_components.new_bestway_spa.coordinator import BestwayUpdateCoordinator
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    from custom_components.new_bestway_spa.const import DOMAIN

    # Create a mock config entry for the coordinator
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"device_id": "test_device_123"},
    )

    coordinator = BestwayUpdateCoordinator(
        hass=hass,
        config_entry=mock_entry,
        api=mock_api,
        device_id="test_device_123",
        update_interval=timedelta(seconds=60),
    )

    # Set initial test data
    coordinator.data = {
        "power_state": 1,
        "heater_state": 0,
        "filter_state": 0,
        "wave_state": 0,
        "hydrojet_state": 0,
        "water_temperature": 22,
        "temperature_setting": 28,
        "temperature_unit": 1,  # Celsius
        "is_online": True,
        "error_code": 0,
        "warning": 0,
        "locked": 0,
        "wifi_version": "1.0.0",
        "mcu_version": "2.0.0",
        "trd_version": "3.0.0",
        "ota_status": "idle",
        "connect_type": "wifi",
    }

    # Mock last_update_success
    coordinator._attr_last_update_success = True

    return coordinator
