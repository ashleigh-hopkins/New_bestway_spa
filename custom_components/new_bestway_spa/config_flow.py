import logging
import secrets
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .spa_api import authenticate, BestwaySpaAPI, generate_visitor_id

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        """Initialize config flow."""
        super().__init__()
        self._visitor_id = None
        self._token = None

    async def async_step_user(self, user_input=None):
        """Handle initial step - offer QR code or manual setup."""
        # Redirect to QR code setup as primary method
        return await self.async_step_qr_code()

    async def async_step_qr_code(self, user_input=None):
        """Configure device via QR code scan or existing visitor ID.

        Two modes:
        1. Existing Account: Provide visitor_id → Skip QR, use existing account
        2. New Account: Leave visitor_id blank → Require QR code, generate new account

        This supports both new users (QR) and existing users (visitor_id).
        """
        errors = {}

        if user_input is not None:
            qr_code = user_input.get("qr_code", "").strip()
            provided_visitor_id = user_input.get("visitor_id", "").strip()

            # Determine setup mode
            if provided_visitor_id:
                # Mode 1: User provided existing visitor_id
                _LOGGER.info("Using provided visitor_id (existing account)")
                self._visitor_id = provided_visitor_id
                client_id = (
                    secrets.token_urlsafe(11)[:15]
                    .replace("-", "")
                    .replace("_", "")
                    .lower()
                )

                # No QR code needed - skip binding, go straight to discovery

            else:
                # Mode 2: No visitor_id provided, require QR code
                if not qr_code:
                    errors["base"] = "qr_code_required"
                    return self.async_show_form(
                        step_id="qr_code",
                        data_schema=vol.Schema(
                            {
                                vol.Optional("visitor_id"): str,
                                vol.Optional("qr_code"): str,
                            }
                        ),
                        errors=errors,
                    )

                # Validate QR format
                if not qr_code.startswith("RW_Share_"):
                    errors["qr_code"] = "invalid_format"
                    return self.async_show_form(
                        step_id="qr_code",
                        data_schema=vol.Schema(
                            {
                                vol.Optional("visitor_id"): str,
                                vol.Optional("qr_code"): str,
                            }
                        ),
                        errors=errors,
                    )

                # Generate new visitor credentials
                _LOGGER.info("Generating new visitor_id from QR code")
                self._visitor_id = generate_visitor_id()
                client_id = (
                    secrets.token_urlsafe(11)[:15]
                    .replace("-", "")
                    .replace("_", "")
                    .lower()
                )

            # Prepare authentication config
            config = {
                "visitor_id": self._visitor_id,
                "client_id": client_id,
                "registration_id": "",
                "push_type": "fcm",
                "location": "GB",
            }

            # Use Home Assistant's shared session
            try:
                session = async_get_clientsession(self.hass)

                # Authenticate
                self._token = await authenticate(session, config)

                if not self._token:
                    _LOGGER.error(
                        "Authentication returned no token for visitor_id: %s",
                        self._visitor_id[:8],
                    )
                    errors["base"] = "auth_failed"
                    return self.async_show_form(
                        step_id="qr_code",
                        data_schema=vol.Schema(
                            {
                                vol.Optional("visitor_id"): str,
                                vol.Optional("qr_code"): str,
                            }
                        ),
                        errors=errors,
                    )

                # Bind device using QR code (only if QR code provided)
                if qr_code:
                    config["token"] = self._token
                    config["device_id"] = "placeholder"
                    config["product_id"] = "placeholder"
                    config["device_name"] = "placeholder"

                    api = BestwaySpaAPI(session, config)
                    device_info = await api.bind_device_qr(qr_code)

                    if not device_info:
                        errors["qr_code"] = "binding_failed"
                        return self.async_show_form(
                            step_id="qr_code",
                            data_schema=vol.Schema(
                                {
                                    vol.Optional("visitor_id"): str,
                                    vol.Optional("qr_code"): str,
                                }
                            ),
                            errors=errors,
                        )

            except Exception as e:
                _LOGGER.error("Configuration exception: %s", str(e), exc_info=True)
                # Determine error type
                if qr_code and "bind" in str(e).lower():
                    errors["qr_code"] = "binding_failed"
                else:
                    errors["base"] = "auth_failed"
                return self.async_show_form(
                    step_id="qr_code",
                    data_schema=vol.Schema(
                        {vol.Optional("visitor_id"): str, vol.Optional("qr_code"): str}
                    ),
                    errors=errors,
                )

            # Success! Proceed to device selection
            # Device selection step will discover devices using visitor_id
            return await self.async_step_select_device()

        # Show setup form with both options
        # Description comes from translations/en.json
        return self.async_show_form(
            step_id="qr_code",
            data_schema=vol.Schema(
                {vol.Optional("visitor_id"): str, vol.Optional("qr_code"): str}
            ),
        )

    async def async_step_manual(self, user_input=None):
        """Manual configuration (fallback for advanced users).

        This preserves the original manual configuration method for edge cases
        where QR code setup isn't available or preferred.
        """
        errors = {}

        if user_input is not None:
            return self.async_create_entry(
                title=user_input["device_name"], data=user_input
            )

        schema = vol.Schema(
            {
                vol.Required("device_name"): str,
                vol.Required("visitor_id"): str,
                vol.Required("registration_id"): str,
                vol.Optional("device_id"): str,
                vol.Optional("product_id"): str,
                vol.Optional("push_type", default="fcm"): vol.In(["fcm", "apns"]),
                vol.Optional("client_id"): str,
                vol.Optional("api_host", default="smarthub-eu.bestwaycorp.com"): str,
                vol.Optional("location", default="GB"): str,
            }
        )

        return self.async_show_form(step_id="manual", data_schema=schema, errors=errors)

    async def async_step_select_device(self, user_input=None):
        """Select device from discovered devices.

        Shows picker with all devices found via discovery API.
        Auto-populates all configuration fields from selected device:
        - device_id, product_id, service_region (from device metadata)
        - visitor_id, token (from QR flow)

        This completes the zero-configuration setup experience.
        """

        # Ensure we have credentials from QR flow
        if not self._visitor_id or not self._token:
            return self.async_abort(reason="setup_incomplete")

        # Create API config for device operations
        config = {
            "visitor_id": self._visitor_id,
            "token": self._token,
            "device_id": "placeholder",
            "product_id": "placeholder",
            "device_name": "placeholder",
            "registration_id": "",
            "push_type": "fcm",
            "location": "GB",
        }

        # Handle device selection
        if user_input is not None:
            selected_device_id = user_input["device_id"]

            # Get full device info
            try:
                session = async_get_clientsession(self.hass)
                api = BestwaySpaAPI(session, config)
                device = await api.get_device_info(selected_device_id)

                if not device:
                    return self.async_abort(reason="device_not_found")

                # Extract device name (API may use device_name, device_alias, or nick_name)
                device_name = (
                    device.get("device_name")
                    or device.get("device_alias")
                    or device.get("nick_name")
                    or "Bestway Spa"
                )

                # Create config entry with all auto-populated fields
                return self.async_create_entry(
                    title=device_name,
                    data={
                        # Credentials from QR flow
                        "visitor_id": self._visitor_id,
                        "token": self._token,
                        "registration_id": "",  # Not needed with visitor auth
                        "client_id": "",  # Not needed with visitor auth
                        "push_type": "fcm",
                        # Device details from discovery (auto-populated!)
                        "device_id": device["device_id"],
                        "product_id": device.get(
                            "product_id", "T53NN8"
                        ),  # Fallback to common type
                        "product_series": device.get(
                            "product_series", ""
                        ).strip(),  # e.g., "AIRJET"
                        "service_region": device.get(
                            "service_region", "eu-central-1"
                        ),  # Fallback to EU
                        "device_name": device_name,
                        # Optional fields
                        "api_host": "smarthub-eu.bestwaycorp.com",
                        "location": "GB",
                    },
                )

            except Exception as e:
                _LOGGER.error("Error getting device info: %s", str(e))
                return self.async_abort(reason="device_not_found")

        # Discover devices
        try:
            session = async_get_clientsession(self.hass)
            api = BestwaySpaAPI(session, config)
            devices = await api.discover_devices()

            if not devices:
                return self.async_abort(reason="no_devices_found")

            # Build device picker options
            # Format: "Device Name (Product ID)" with online status indicator
            device_options = {}
            for device in devices:
                device_id = device["device_id"]
                device_name = (
                    device.get("device_name")
                    or device.get("device_alias")
                    or device.get("nick_name")
                    or "Unknown Device"
                )
                product_id = device.get("product_id", "Unknown")
                is_online = device.get("is_online", False)

                # Add online indicator
                status_indicator = "🟢" if is_online else "🔴"

                # Format: "🟢 Device Name (Product ID)"
                display_name = f"{status_indicator} {device_name} ({product_id})"

                device_options[device_id] = display_name

            # Show device picker
            return self.async_show_form(
                step_id="select_device",
                data_schema=vol.Schema(
                    {vol.Required("device_id"): vol.In(device_options)}
                ),
            )

        except Exception as e:
            _LOGGER.error("Device discovery failed: %s", str(e))
            return self.async_abort(reason="no_devices_found")
