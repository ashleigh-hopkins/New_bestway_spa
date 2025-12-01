"""Fixtures for Bestway Spa integration tests."""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock


@pytest.fixture
def mock_api():
    """Mock BestwaySpaAPI for testing."""
    with patch("custom_components.new_bestway_spa.spa_api.BestwaySpaAPI") as mock:
        api_instance = mock.return_value

        # Mock get_status response (from real device)
        api_instance.get_status = AsyncMock(return_value={
            "power_state": 1,
            "heater_state": 0,
            "filter_state": 0,
            "wave_state": 0,
            "water_temperature": 22,
            "temperature_setting": 28,
            "temperature_unit": 1,
            "is_online": True,
            "error_code": ""
        })

        # Mock set_state response
        api_instance.set_state = AsyncMock(return_value={
            "code": 0,
            "message": "SUCCESS"
        })

        # Mock discover_devices response (test data, no real device IDs)
        api_instance.discover_devices = AsyncMock(return_value=[
            {
                "device_id": "test_device_123abc",
                "device_alias": "Test Spa",
                "product_id": "T53NN8",
                "service_region": "eu-central-1",
                "is_online": True
            }
        ])

        # Mock get_device_info
        api_instance.get_device_info = AsyncMock(return_value={
            "device_id": "test_device_123abc",
            "device_alias": "Test Spa",
            "product_id": "T53NN8",
            "service_region": "eu-central-1",
            "is_online": True
        })

        # Mock bind_device_qr (success case)
        api_instance.bind_device_qr = AsyncMock(return_value={
            "device_id": "test_device_123abc",
            "name": "Test Spa",
            "binding_role": 3
        })

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
