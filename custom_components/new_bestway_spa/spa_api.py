import logging
import hashlib
import random
import string
import time
import json
import secrets
import aiohttp

from .encryption import encrypt_command_payload

_LOGGER = logging.getLogger(__name__)


def generate_visitor_id():
    """Generate cryptographically secure random visitor ID.

    Returns:
        str: 16-character hex string (e.g., "1a2b3c4d5e6f7890")

    Example:
        >>> visitor_id = generate_visitor_id()
        >>> len(visitor_id)
        16
        >>> all(c in '0123456789abcdef' for c in visitor_id)
        True
    """
    return secrets.token_hex(8)


async def authenticate(session, config):
    api_host = config.get("api_host", "smarthub-eu.bestwaycorp.com")
    BASE_URL = "https://" + api_host
    APPID = "AhFLL54HnChhrxcl9ZUJL6QNfolTIB"
    APPSECRET = "4ECvVs13enL5AiYSmscNjvlaisklQDz7vWPCCWXcEFjhWfTmLT"

    def generate_auth():
        nonce = ''.join(random.choices(string.ascii_lowercase + string.digits, k=32))
        ts = str(int(time.time()))
        sign = hashlib.md5((APPID + APPSECRET + nonce + ts).encode("utf-8")).hexdigest().upper()
        return nonce, ts, sign

    push_type = config.get("push_type", "fcm")

    payload = {
        "app_id": APPID,
        "lan_code": "en",
        "location": config.get("location", "GB"),
        "push_type": push_type,
        "timezone": "GMT",
        "visitor_id": config["visitor_id"],
        "registration_id": config["registration_id"]
    }

    if push_type == "fcm":
        payload["client_id"] = config["client_id"]

    nonce, ts, sign = generate_auth()
    headers = {
        "pushtype": push_type,
        "appid": APPID,
        "nonce": nonce,
        "ts": ts,
        "accept-language": "en",
        "sign": sign,
        "Authorization": "token",
        "Host": api_host,
        "Connection": "Keep-Alive",
        "User-Agent": "okhttp/4.9.0",
        "Content-Type": "application/json; charset=UTF-8"
    }

    _LOGGER.debug("Authenticating with payload: %s", payload)

    async with session.post(
        f"{BASE_URL}/api/enduser/visitor",
        headers=headers,
        json=payload,
        ssl=False
    ) as resp:
        data = await resp.json()
        _LOGGER.debug("Auth response: %s", data)
        return data.get("data", {}).get("token")


class BestwaySpaAPI:
    APPID = "AhFLL54HnChhrxcl9ZUJL6QNfolTIB"
    APPSECRET = "4ECvVs13enL5AiYSmscNjvlaisklQDz7vWPCCWXcEFjhWfTmLT"

    def __init__(self, session: aiohttp.ClientSession, config: dict):
        self.api_host = config.get("api_host", "smarthub-eu.bestwaycorp.com")
        self.BASE_URL = "https://" + self.api_host
        self.session = session
        self.token = config["token"]
        self.device_id = config.get("device_id") or config["device_name"]
        self.product_id = config.get("product_id") or config["device_name"]
        self.client_id = config.get("client_id")
        self.registration_id = config.get("registration_id")
        self.push_type = config.get("push_type", "fcm")

    def _generate_auth_headers(self):
        nonce = ''.join(random.choices(string.ascii_lowercase + string.digits, k=32))
        ts = str(int(time.time()))
        sign = hashlib.md5((self.APPID + self.APPSECRET + nonce + ts).encode("utf-8")).hexdigest().upper()
        return {
            "pushtype": self.push_type,
            "appid": self.APPID,
            "nonce": nonce,
            "ts": ts,
            "accept-language": "en",
            "sign": sign,
            "Authorization": f"token {self.token}",
            "Host": self.api_host,
            "Connection": "Keep-Alive",
            "User-Agent": "okhttp/4.9.0",
            "Content-Type": "application/json; charset=UTF-8"
        }

    async def get_status(self):
        payload = {
            "device_id": self.device_id,
            "product_id": self.product_id
        }

        _LOGGER.debug("Sending get_status payload: %s", payload)

        async with self.session.post(
            f"{self.BASE_URL}/api/device/thing_shadow/",
            headers=self._generate_auth_headers(),
            json=payload,
            ssl=False
        ) as resp:
            data = await resp.json()
            _LOGGER.debug("Full API response: %s", data)

            raw_data = data.get("data", {})
            _LOGGER.debug("Raw data from API: %s", raw_data)

            if "state" in raw_data:
                if "reported" in raw_data["state"]:
                    device_state = raw_data["state"]["reported"]
                    _LOGGER.debug("Found reported state: %s", device_state)
                elif "desired" in raw_data["state"]:
                    device_state = raw_data["state"]["desired"]
                    _LOGGER.debug("Found desired state: %s", device_state)
                else:
                    device_state = raw_data["state"]
                    _LOGGER.debug("Found state object: %s", device_state)
            else:
                device_state = raw_data

            # ✅ Normalize keys to match sensor keys
            # Normalize warning/error_code: treat empty string "" same as 0
            warning = device_state.get("warning")
            error_code = device_state.get("error_code")

            mapped = {
                "wifi_version": device_state.get("wifivertion"),
                "ota_status": device_state.get("otastatus"),
                "mcu_version": device_state.get("mcuversion"),
                "trd_version": device_state.get("trdversion"),
                "connect_type": device_state.get("ConnectType"),
                "power_state": device_state.get("power_state"),
                "heater_state": device_state.get("heater_state"),
                "wave_state": device_state.get("wave_state"),
                "filter_state": device_state.get("filter_state"),
                "temperature_setting": device_state.get("temperature_setting"),
                "temperature_unit": device_state.get("temperature_unit"),
                "water_temperature": device_state.get("water_temperature"),
                "warning": 0 if warning == "" else warning,
                "error_code": 0 if error_code == "" else error_code,
                "hydrojet_state": device_state.get("hydrojet_state"),
                "is_online": device_state.get("is_online")
            }

            _LOGGER.debug("Normalized data: %s", mapped)
            return mapped

    async def set_state(self, key, value, use_v2=True):
        """Send control command to device.

        Args:
            key: Command key (e.g., 'power_state', 'heater_state', 'temperature_setting')
            value: Command value (0/1 for booleans, integer for temperature)
            use_v2: Use v2 API endpoint (default True). Falls back to v1 on error.

        Returns:
            API response dict with 'code' and 'message' fields
        """
        if isinstance(value, bool):
            value = int(value)

        # Try v2 API first (modern, encrypted)
        if use_v2:
            try:
                _LOGGER.debug("Attempting v2 API endpoint")

                # Generate fresh headers (includes signature needed for encryption)
                headers = self._generate_auth_headers()
                sign = headers["sign"]

                # Build AWS IoT Device Shadow format
                # CRITICAL: "desired" field must be a JSON STRING, not an object
                desired_json_string = json.dumps({
                    "state": {
                        "desired": {key: value}
                    }
                }, separators=(",", ":"))

                # Build plaintext payload for encryption
                command_payload = {
                    "device_id": self.device_id,
                    "product_id": self.product_id,
                    "desired": desired_json_string  # JSON string!
                }

                # Serialize and encrypt
                plaintext = json.dumps(command_payload, separators=(",", ":"))
                encrypted_data = encrypt_command_payload(sign, self.APPSECRET, plaintext)

                body = {"encrypted_data": encrypted_data}

                _LOGGER.debug("Sending v2 encrypted command: %s=%s", key, value)

                # Send to v2 endpoint
                async with self.session.post(
                    f"{self.BASE_URL}/api/v2/device/command",
                    headers=headers,
                    json=body,
                    ssl=False
                ) as resp:
                    response = await resp.json()

                    if response.get("code") == 0:
                        _LOGGER.info("✓ v2 API success: %s=%s", key, value)
                        return response
                    else:
                        _LOGGER.warning("v2 API returned error code %s, falling back to v1", response.get("code"))

            except Exception as e:
                _LOGGER.warning("v2 API error (%s), falling back to v1", str(e))

        # v1 API fallback (preserves existing reliability)
        _LOGGER.debug("Using v1 API endpoint")

        payload = {
            "device_id": self.device_id,
            "product_id": self.product_id,
            "desired": {
                "state": {
                    "desired": {
                        key: value
                    }
                }
            }
        }

        _LOGGER.debug("Sending v1 set_state payload: %s", payload)

        async with self.session.post(
            f"{self.BASE_URL}/api/device/command/",
            headers=self._generate_auth_headers(),
            json=payload,
            ssl=False
        ) as resp:
            response = await resp.json()
            _LOGGER.info("✓ v1 API success: %s=%s", key, value)
            _LOGGER.debug("v1 set_state response: %s", response)
            return response

    async def discover_devices(self):
        """Discover all devices via home/room/device hierarchy.

        Traverses the complete hierarchy:
        1. GET /api/enduser/homes - Get all homes
        2. For each home: GET /api/enduser/home/rooms?home_id=X
        3. For each room: GET /api/enduser/home/room/devices?room_id=Y

        Returns:
            List[dict]: All discovered devices with metadata including:
            - device_id: Unique device identifier
            - device_alias or nick_name: Device name
            - product_id: Product type (e.g., "T53NN8")
            - service_region: AWS region (e.g., "eu-central-1")
            - is_online: Connection status
            - Plus additional device metadata from API
        """
        all_devices = []

        # Step 1: Get homes
        _LOGGER.debug("Discovering devices: fetching homes...")

        async with self.session.get(
            f"{self.BASE_URL}/api/enduser/homes",
            headers=self._generate_auth_headers(),
            ssl=False
        ) as resp:
            homes_result = await resp.json()

        if homes_result.get("code") != 0:
            _LOGGER.error("Failed to get homes: %s", homes_result.get("message"))
            return []

        homes = homes_result.get("data", {}).get("list", [])
        _LOGGER.debug("Found %d home(s)", len(homes))

        if not homes:
            _LOGGER.warning("No homes found for this account")
            return []

        # Step 2: For each home, get rooms
        for home in homes:
            home_id = home.get("id")
            home_name = home.get("name", "Unknown")
            _LOGGER.debug("Processing home: %s (id=%s)", home_name, home_id)

            async with self.session.get(
                f"{self.BASE_URL}/api/enduser/home/rooms?home_id={home_id}",
                headers=self._generate_auth_headers(),
                ssl=False
            ) as resp:
                rooms_result = await resp.json()

            if rooms_result.get("code") != 0:
                _LOGGER.warning("Failed to get rooms for home %s: %s",
                              home_id, rooms_result.get("message"))
                continue

            rooms = rooms_result.get("data", {}).get("list", [])
            _LOGGER.debug("Found %d room(s) in home %s", len(rooms), home_name)

            # Step 3: For each room, get devices
            for room in rooms:
                room_id = room.get("id")
                room_name = room.get("name", "Unknown")
                _LOGGER.debug("Processing room: %s (id=%s)", room_name, room_id)

                async with self.session.get(
                    f"{self.BASE_URL}/api/enduser/home/room/devices?room_id={room_id}",
                    headers=self._generate_auth_headers(),
                    ssl=False
                ) as resp:
                    devices_result = await resp.json()

                if devices_result.get("code") != 0:
                    _LOGGER.warning("Failed to get devices for room %s: %s",
                                  room_id, devices_result.get("message"))
                    continue

                devices = devices_result.get("data", {}).get("list", [])
                _LOGGER.debug("Found %d device(s) in room %s", len(devices), room_name)

                # Debug: Log device fields to identify naming field
                for device in devices:
                    _LOGGER.debug("Device fields: %s", {k: v for k, v in device.items() if 'name' in k.lower() or 'alias' in k.lower()})

                all_devices.extend(devices)

        _LOGGER.info("Discovery complete: found %d total device(s)", len(all_devices))
        return all_devices

    async def get_device_info(self, device_id: str):
        """Get specific device info by device_id.

        Args:
            device_id: Device ID to search for

        Returns:
            dict: Device metadata if found, None otherwise
        """
        _LOGGER.debug("Looking up device: %s", device_id)

        devices = await self.discover_devices()

        for device in devices:
            if device.get("device_id") == device_id:
                _LOGGER.debug("Found device: %s", device.get("device_name") or device.get("device_alias") or device.get("nick_name"))
                return device

        _LOGGER.warning("Device not found: %s", device_id)
        return None

    async def bind_device_qr(self, qr_code: str):
        """Bind device to visitor account using QR code.

        This allows users to add devices by scanning the QR code displayed on
        the spa's control panel, eliminating the need for MITM proxy credential capture.

        QR Code Format: RW_Share_<vercode>
        Example: RW_Share_abc123def456xyz789_abc123def456xyz789

        Args:
            qr_code: Full QR code string (must start with "RW_Share_")

        Returns:
            dict: Device info if successful, containing:
                - enduser_id: User account ID
                - device_id: Device identifier
                - name: Device name
                - binding_time: When device was bound (ISO 8601)
                - binding_type: Type of binding (typically "home")
                - binding_role: User's permission level (1=Owner, 2=Admin, 3=User)
                - software_version: Device firmware version
            None: If binding failed

        API Errors:
            - Code 4001: Invalid or expired QR code
            - Code 4002: QR code already used
            - Code 401: Authentication error (invalid token)

        Note: QR codes are time-limited and single-use. Generate fresh QR code
        from spa display if binding fails.
        """
        # Validate QR code format
        if not qr_code or not isinstance(qr_code, str):
            _LOGGER.error("QR code must be a non-empty string")
            return None

        if not qr_code.startswith("RW_Share_"):
            _LOGGER.error("Invalid QR code format. Expected 'RW_Share_<vercode>', got: %s", qr_code[:20])
            return None

        vercode_part = qr_code[9:]  # Strip "RW_Share_" prefix
        if not vercode_part:
            _LOGGER.error("QR code missing vercode part")
            return None

        _LOGGER.info("Binding device with QR code: %s...", qr_code[:25])

        # Prepare request
        payload = {
            "vercode": qr_code,  # Send full QR code including prefix
            "push_type": self.push_type
        }

        _LOGGER.debug("Grant device payload: %s", payload)

        # Call grant_device API
        try:
            async with self.session.post(
                f"{self.BASE_URL}/api/enduser/grant_device/",
                headers=self._generate_auth_headers(),
                json=payload,
                ssl=False
            ) as resp:
                result = await resp.json()

            _LOGGER.debug("Grant device response: %s", result)

            # Check response code
            code = result.get("code")

            if code == 0:
                # Success
                device_info = result.get("data", {})
                device_name = device_info.get("name", "Unknown")
                device_id = device_info.get("device_id", "Unknown")
                _LOGGER.info("✓ Device bound successfully: %s (id=%s)", device_name, device_id[:20])
                return device_info

            elif code == 4001:
                _LOGGER.error("QR code invalid or expired. Generate fresh QR code from spa display.")
                return None

            elif code == 4002:
                _LOGGER.error("QR code already used. Each QR code is single-use only.")
                return None

            else:
                _LOGGER.error("Grant device failed: code=%s, message=%s", code, result.get("message"))
                return None

        except Exception as e:
            _LOGGER.error("Grant device request failed: %s", str(e))
            return None
