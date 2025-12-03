"""WebSocket client for Bestway Smart Spa real-time updates.

This module implements AWS IoT WebSocket connection for near-instant device
state updates, replacing 30-second polling with push notifications.

Architecture: Device → AWS IoT Core → AWS API Gateway → WebSocket → Home Assistant

Based on reverse engineering of official Bestway Smart Spa app:
- Regional endpoints from ServiceConfig.java (lines 28-32)
- Heartbeat logic from WsManager.java (lines 118-142)
- Reconnection strategy from WsManager.java (lines 356-382)

Reference: layzspa-aws-iot/docs/aws-iot/WEBSOCKET.md
"""

import asyncio
import json
import logging
import time
from typing import Callable, Optional

import websockets
from websockets.client import ClientProtocol

from homeassistant.util import ssl as ssl_util

_LOGGER = logging.getLogger(__name__)


class BestwayWebSocket:
    """WebSocket client for AWS IoT real-time device updates.

    Provides near-instant state synchronization by connecting to AWS API Gateway
    WebSocket endpoint and receiving device shadow updates pushed from AWS IoT Core.

    Features:
    - Regional endpoint selection (EU, US, China)
    - 30-second heartbeat to maintain connection
    - Exponential backoff reconnection (3s → 60s max)
    - Graceful error handling and degradation
    """

    # Regional WebSocket endpoints (from ServiceConfig.java lines 28-32)
    ENDPOINTS = {
        "eu-central-1": "wss://7lv67j5lbh.execute-api.eu-central-1.amazonaws.com/prod",
        "us-west-1": "wss://9i661wi8f9.execute-api.us-west-1.amazonaws.com/prod",
        "cn-north-1": "wss://fu9gsv4dxh.execute-api.cn-north-1.amazonaws.com.cn/prod",
    }

    # Heartbeat configuration (from WsManager.java lines 118-142)
    HEARTBEAT_INTERVAL = 30  # seconds
    HEARTBEAT_TIMEOUT = 40  # seconds
    MAX_HEARTBEAT_FAILURES = 3

    # Reconnection configuration (from WsManager.java lines 356-382)
    RECONNECT_DELAYS = [3, 6, 12, 24, 48, 60]  # seconds, exponential backoff

    def __init__(
        self,
        device_id: str,
        service_region: str,
        token: str,
        callback: Callable[[dict], None],
        token_refresh_callback: Optional[Callable[[], str]] = None,
    ):
        """Initialize WebSocket client.

        Args:
            device_id: Device ID for shadow subscription
            service_region: AWS region (e.g., "eu-central-1")
            token: JWT authentication token
            callback: Function to call with state updates (receives dict)
            token_refresh_callback: Optional async function to refresh token on auth failure
        """
        self.device_id = device_id
        self.service_region = service_region
        self.token = token
        self.callback = callback
        self.token_refresh_callback = token_refresh_callback

        self.websocket: Optional[ClientProtocol] = None
        self._running = False
        self._seq_id = int(time.time() * 1000)
        self._heartbeat_failures = 0
        self._reconnect_count = 0
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._listen_task: Optional[asyncio.Task] = None

    @property
    def ws_url(self) -> str:
        """Build WebSocket URL for device's region.

        Returns:
            WebSocket URL for the specified region, or EU as fallback
        """
        endpoint = self.ENDPOINTS.get(self.service_region)

        if not endpoint:
            _LOGGER.warning("Unknown region %s, defaulting to EU", self.service_region)
            endpoint = self.ENDPOINTS["eu-central-1"]

        return endpoint

    async def connect(self):
        """Connect to WebSocket and start listening.

        Establishes connection to regional AWS API Gateway endpoint and
        starts heartbeat and message listening tasks.

        Uses Authorization header for authentication (matching official app behavior
        from WsManager.java line 83: addHeader("Authorization", token)).
        """
        try:
            _LOGGER.info(
                "Connecting WebSocket for device %s (region: %s)",
                self.device_id[:20],
                self.service_region,
            )

            # Use Home Assistant's pre-cached SSL context (avoids blocking warnings)
            ssl_context = ssl_util.get_default_context()

            # Connect with Authorization header (matches official app and reference)
            # Note: websockets>=15.0 uses 'additional_headers' parameter
            self.websocket = await websockets.connect(
                self.ws_url,
                additional_headers={"Authorization": self.token},
                ssl=ssl_context,
                ping_interval=None,  # Manual heartbeat
            )

            self._running = True
            self._heartbeat_failures = 0
            self._reconnect_count = 0

            _LOGGER.info("✓ WebSocket connected: %s", self.service_region)

            # Start background tasks
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            self._listen_task = asyncio.create_task(self._listen_loop())

        except Exception as err:
            error_msg = str(err)
            _LOGGER.error("WebSocket connection failed: %s", error_msg)

            # If HTTP 400 and we have token refresh callback, try refreshing token
            if "HTTP 400" in error_msg and self.token_refresh_callback:
                _LOGGER.info(
                    "HTTP 400 detected - attempting token refresh and immediate retry"
                )
                try:
                    new_token = await self.token_refresh_callback()
                    if new_token:
                        self.token = new_token
                        _LOGGER.info(
                            "Token refreshed successfully, retrying connection immediately"
                        )
                        # Reset reconnect count since we got a fresh token
                        self._reconnect_count = 0
                        # Retry connection immediately instead of scheduling with delay
                        await self.connect()
                        return  # If successful, don't schedule another reconnect
                except Exception as refresh_err:
                    _LOGGER.error("Token refresh or retry failed: %s", str(refresh_err))

            await self._schedule_reconnect()

    async def _heartbeat_loop(self):
        """Send heartbeat every 30 seconds to keep connection alive.

        Sends both application-level heartbeat message (JSON) and
        WebSocket protocol PING frame as per official app behavior.

        Triggers reconnection after 3 consecutive failures.
        """
        while self._running:
            await asyncio.sleep(self.HEARTBEAT_INTERVAL)

            try:
                await self._send_heartbeat()
                self._heartbeat_failures = 0

            except Exception as err:
                _LOGGER.warning("Heartbeat failed: %s", str(err))
                self._heartbeat_failures += 1

                if self._heartbeat_failures >= self.MAX_HEARTBEAT_FAILURES:
                    _LOGGER.error(
                        "Max heartbeat failures (%d) reached, reconnecting",
                        self.MAX_HEARTBEAT_FAILURES,
                    )
                    await self._schedule_reconnect()
                    break

    async def _send_heartbeat(self):
        """Send heartbeat message (application-level + WebSocket PING).

        Heartbeat format from WsManager.java lines 118-142 (decompiled APK).
        Sends both JSON message and protocol PING frame.
        """
        if not self.websocket:
            return

        # Application-level heartbeat (JSON message format from decompiled APK)
        message = {
            "action": "heartbeat",
            "req_event": "heartbeat_req",
            "seq_id": self._next_seq_id(),
            "req_count": 1,
            "req": None,
        }

        await self.websocket.send(json.dumps(message))

        # Also send WebSocket protocol PING frame (as per official app)
        await self.websocket.ping()

        _LOGGER.debug("Heartbeat sent (seq_id=%d)", message["seq_id"])

    async def _listen_loop(self):
        """Listen for incoming WebSocket messages.

        Processes device shadow updates and triggers state callback.
        Handles connection closure and errors with automatic reconnection.
        """
        try:
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    await self._handle_message(data)

                except json.JSONDecodeError:
                    _LOGGER.warning("Received malformed JSON message")

        except websockets.exceptions.ConnectionClosed:
            _LOGGER.warning("WebSocket connection closed unexpectedly")
            # Immediate reconnection attempt on connection drop (no delay)
            # If it fails due to token expiry, token refresh will handle it
            self._reconnect_count = 0  # Reset for immediate retry
            await self._schedule_reconnect()

        except Exception as err:
            _LOGGER.error("WebSocket listen error: %s", str(err))
            await self._schedule_reconnect()

    async def _handle_message(self, data: dict):
        """Process incoming WebSocket message.

        Extracts device state from shadow updates and calls callback.

        Args:
            data: Parsed JSON message from WebSocket
        """
        # Device shadow update
        if "state" in data and "reported" in data.get("state", {}):
            state = data["state"]["reported"]

            # Add device metadata if present
            if "device_id" in data:
                state["device_id"] = data["device_id"]
            if "product_id" in data:
                state["product_id"] = data["product_id"]

            _LOGGER.debug(
                "Received state update for device %s: %d fields",
                self.device_id[:20],
                len(state),
            )

            # Call update callback
            if self.callback is not None:
                try:
                    self.callback(state)
                except Exception as err:
                    _LOGGER.error("Callback error: %s", str(err))

    async def _schedule_reconnect(self):
        """Schedule reconnection with exponential backoff.

        Backoff strategy from WsManager.java lines 356-382:
        - Attempt 1: 3s
        - Attempt 2: 6s
        - Attempt 3: 12s
        - Attempt 4: 24s
        - Attempt 5: 48s
        - Attempt 6+: 60s (max)
        """
        if not self._running:
            return

        # Calculate delay with exponential backoff
        if self._reconnect_count < len(self.RECONNECT_DELAYS):
            delay = self.RECONNECT_DELAYS[self._reconnect_count]
        else:
            delay = self.RECONNECT_DELAYS[-1]  # Use max delay (60s)

        self._reconnect_count += 1

        _LOGGER.info("Reconnecting in %ds (attempt %d)", delay, self._reconnect_count)

        await asyncio.sleep(delay)

        # Close current connection
        await self.disconnect()

        # Reconnect
        await self.connect()

    def _next_seq_id(self) -> int:
        """Generate next sequence ID for heartbeat messages.

        Returns:
            Timestamp in milliseconds
        """
        self._seq_id = int(time.time() * 1000)
        return self._seq_id

    async def disconnect(self):
        """Disconnect WebSocket and stop all tasks.

        Cleanly shuts down heartbeat and listen tasks, then closes connection.
        """
        _LOGGER.info("Disconnecting WebSocket for device %s", self.device_id[:20])

        self._running = False

        # Cancel background tasks
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        if self._listen_task and not self._listen_task.done():
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass

        # Close WebSocket connection
        if self.websocket:
            await self.websocket.close()
            self.websocket = None

        _LOGGER.info("✓ WebSocket disconnected")
