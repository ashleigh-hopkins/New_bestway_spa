"""Test config flow with Home Assistant fixtures."""

import pytest
from unittest.mock import patch, AsyncMock
from homeassistant.data_entry_flow import FlowResultType

from custom_components.new_bestway_spa.config_flow import ConfigFlow


pytestmark = pytest.mark.asyncio


async def test_qr_code_invalid_format(hass):
    """Test QR code validation rejects invalid format."""
    flow = ConfigFlow()
    flow.hass = hass

    # Submit invalid QR code
    result = await flow.async_step_qr_code({"qr_code": "INVALID_CODE"})

    # Should show form again with error
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "qr_code"
    assert "qr_code" in result["errors"]
    assert result["errors"]["qr_code"] == "invalid_format"


async def test_device_selection(hass, mock_api):
    """Test device selection step - shows device picker form."""
    flow = ConfigFlow()
    flow.hass = hass
    flow._visitor_id = "test_visitor_123"
    flow._token = "test_token_123"

    # Mock HA session helper and API
    with patch(
        "custom_components.new_bestway_spa.config_flow.async_get_clientsession"
    ) as mock_session_func:
        mock_session = AsyncMock()
        mock_session_func.return_value = mock_session

        with patch(
            "custom_components.new_bestway_spa.config_flow.BestwaySpaAPI"
        ) as mock_api_class:
            mock_api_class.return_value = mock_api

            # Show device picker
            result = await flow.async_step_select_device()

            assert result["type"] == FlowResultType.FORM
            assert result["step_id"] == "select_device"
            assert "device_id" in result["data_schema"].schema

            # Verify device options format
            mock_api.discover_devices.assert_called_once()


async def test_device_selection_creates_entry(hass, mock_api):
    """Test device selection creates config entry with auto-populated fields."""
    flow = ConfigFlow()
    flow.hass = hass
    flow._visitor_id = "test_visitor_123"
    flow._token = "test_token_123"

    # Mock HA session helper and API
    with patch(
        "custom_components.new_bestway_spa.config_flow.async_get_clientsession"
    ) as mock_session_func:
        mock_session = AsyncMock()
        mock_session_func.return_value = mock_session

        with patch(
            "custom_components.new_bestway_spa.config_flow.BestwaySpaAPI"
        ) as mock_api_class:
            mock_api_class.return_value = mock_api

            # Select device
            result = await flow.async_step_select_device(
                {"device_id": "test_device_123abc"}
            )

            # Should create entry
            assert result["type"] == FlowResultType.CREATE_ENTRY
            assert result["title"] == "Test Spa"

            # Verify all fields auto-populated
            data = result["data"]
            assert data["visitor_id"] == "test_visitor_123"
            assert data["token"] == "test_token_123"
            assert data["device_id"] == "test_device_123abc"
            assert data["product_id"] == "T53NN8"
            assert data["service_region"] == "eu-central-1"
            assert data["device_name"] == "Test Spa"


async def test_manual_config_flow_preserved(hass):
    """Test manual configuration flow still available."""
    flow = ConfigFlow()
    flow.hass = hass

    # Show manual form
    result = await flow.async_step_manual()

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "manual"

    # Verify required fields present
    schema = result["data_schema"].schema
    assert "device_name" in str(schema)
    assert "visitor_id" in str(schema)
