"""Test New Bestway Spa setup process."""

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.new_bestway_spa import (
    BestwayUpdateCoordinator,
    async_unload_entry,
)
from custom_components.new_bestway_spa.const import DOMAIN


async def test_setup_unload_entry(hass: HomeAssistant, bypass_auth, bypass_get_data):
    """Test entry setup and unload."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "visitor_id": "test_visitor_123",
            "device_id": "test_device_123abc",
            "device_name": "Test Spa",
            "product_id": "T53NN8",
            "product_series": "AIRJET",
            "service_region": "eu-central-1",
            "registration_id": "",
        },
        entry_id="test",
    )
    config_entry.add_to_hass(hass)

    # Set up the entry and assert that the values set during setup are where we expect them
    await hass.config_entries.async_setup(config_entry.entry_id)

    assert DOMAIN in hass.data and config_entry.entry_id in hass.data[DOMAIN]
    assert isinstance(
        hass.data[DOMAIN][config_entry.entry_id]["coordinator"],
        BestwayUpdateCoordinator,
    )

    # Unload the entry and verify that the data has been removed
    assert await async_unload_entry(hass, config_entry)
    assert config_entry.entry_id not in hass.data[DOMAIN]


async def test_setup_entry_no_websocket(
    hass: HomeAssistant, bypass_auth, bypass_get_data
):
    """Test entry setup without WebSocket (backward compatibility)."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "visitor_id": "test_visitor_123",
            "device_id": "test_device_123abc",
            "device_name": "Test Spa",
            "product_id": "T53NN8",
            "registration_id": "",
        },
        entry_id="test",
    )
    config_entry.add_to_hass(hass)

    # Set up entry without service_region
    await hass.config_entries.async_setup(config_entry.entry_id)

    assert DOMAIN in hass.data and config_entry.entry_id in hass.data[DOMAIN]

    # Verify no WebSocket in hass.data (backward compatibility mode)
    assert "websocket" not in hass.data[DOMAIN][config_entry.entry_id]


async def test_setup_entry_exception(
    hass: HomeAssistant, bypass_auth, error_on_get_data
):
    """Test setup fails when API raises an exception during entry setup."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "visitor_id": "test_visitor_123",
            "device_id": "test_device_123abc",
            "device_name": "Test Spa",
            "registration_id": "",
        },
        entry_id="test",
    )
    config_entry.add_to_hass(hass)

    # Setup should fail due to error_on_get_data
    result = await hass.config_entries.async_setup(config_entry.entry_id)

    # Verify setup failed
    assert result is False


async def test_unload_entry_with_websocket(
    hass: HomeAssistant, bypass_auth, bypass_get_data
):
    """Test successful integration unload with WebSocket."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "visitor_id": "test_visitor_123",
            "device_id": "test_device_123abc",
            "device_name": "Test Spa",
            "service_region": "eu-central-1",
            "registration_id": "",
        },
        entry_id="test",
    )
    config_entry.add_to_hass(hass)

    # Setup entry
    await hass.config_entries.async_setup(config_entry.entry_id)
    assert DOMAIN in hass.data and config_entry.entry_id in hass.data[DOMAIN]

    # Unload entry
    assert await async_unload_entry(hass, config_entry)
    assert config_entry.entry_id not in hass.data[DOMAIN]
