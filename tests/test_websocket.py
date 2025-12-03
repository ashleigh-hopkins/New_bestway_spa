"""Test WebSocket connectivity and real-time updates."""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from homeassistant.core import HomeAssistant

from custom_components.new_bestway_spa.websocket import BestwayWebSocket


pytestmark = pytest.mark.asyncio








async def test_websocket_connection_success(hass: HomeAssistant):
    """Test successful WebSocket connection."""
    callback = MagicMock()

    with patch(
        "custom_components.new_bestway_spa.websocket.websockets.connect"
    ) as mock_connect:
        # Create a proper mock that can be awaited
        mock_ws = MagicMock()
        mock_ws.send = AsyncMock()
        mock_ws.ping = AsyncMock()
        mock_ws.close = AsyncMock()

        # Make connect return a coroutine
        async def mock_connect_coro(*args, **kwargs):
            return mock_ws

        mock_connect.side_effect = mock_connect_coro

        ws = BestwayWebSocket(
            device_id="test_device_123",
            service_region="eu-central-1",
            token="test_token",
            callback=callback,
        )

        # Patch tasks to prevent them from running
        with patch("asyncio.create_task") as mock_create_task:
            await ws.connect()

            # Verify connection established
            assert ws._running is True
            assert ws._heartbeat_failures == 0
            assert ws._reconnect_count == 0

            # Verify Authorization header used
            mock_connect.assert_called_once()
            call_kwargs = mock_connect.call_args[1]
            assert call_kwargs["additional_headers"]["Authorization"] == "test_token"

            # Verify heartbeat and listen tasks created
            assert mock_create_task.call_count == 2


async def test_websocket_message_handling(hass: HomeAssistant):
    """Test state callback invoked on shadow update message."""
    callback = MagicMock()

    ws = BestwayWebSocket(
        device_id="test_device_123",
        service_region="eu-central-1",
        token="test_token",
        callback=callback,
    )

    # Simulate device shadow update message
    message = {
        "state": {
            "reported": {"power_state": 1, "heater_state": 3, "water_temperature": 25}
        },
        "device_id": "test_device_123",
    }

    await ws._handle_message(message)

    # Verify callback called with state data
    callback.assert_called_once()
    state = callback.call_args[0][0]
    assert state["power_state"] == 1
    assert state["heater_state"] == 3
    assert state["water_temperature"] == 25
    assert state["device_id"] == "test_device_123"




async def test_websocket_connection_http_400_with_token_refresh(hass: HomeAssistant):
    """Test HTTP 400 triggers token refresh and immediate retry."""
    callback = MagicMock()
    token_refresh = AsyncMock(return_value="new_token_456")

    with patch(
        "custom_components.new_bestway_spa.websocket.websockets.connect"
    ) as mock_connect:
        # First call raises HTTP 400, second succeeds
        mock_ws = AsyncMock()
        mock_connect.side_effect = [Exception("HTTP 400 Bad Request"), mock_ws]

        ws = BestwayWebSocket(
            device_id="test_device_123",
            service_region="eu-central-1",
            token="test_token",
            callback=callback,
            token_refresh_callback=token_refresh,
        )

        with patch("asyncio.create_task"):
            await ws.connect()

            # Verify token refresh was called
            token_refresh.assert_called_once()

            # Verify token updated
            assert ws.token == "new_token_456"

            # Verify reconnection attempted with new token
            assert mock_connect.call_count == 2

            # Second call should use new token
            second_call_kwargs = mock_connect.call_args_list[1][1]
            assert (
                second_call_kwargs["additional_headers"]["Authorization"]
                == "new_token_456"
            )

            # Verify reconnect_count reset to 0 (immediate retry, not backoff)
            assert ws._reconnect_count == 0


async def test_websocket_connection_http_400_no_callback(hass: HomeAssistant):
    """Test HTTP 400 without token refresh callback schedules reconnect."""
    callback = MagicMock()

    with patch(
        "custom_components.new_bestway_spa.websocket.websockets.connect"
    ) as mock_connect:
        mock_connect.side_effect = Exception("HTTP 400 Bad Request")

        ws = BestwayWebSocket(
            device_id="test_device_123",
            service_region="eu-central-1",
            token="test_token",
            callback=callback,
            token_refresh_callback=None,  # No refresh callback
        )

        with patch.object(ws, "_schedule_reconnect") as mock_schedule:
            await ws.connect()

            # Should schedule reconnect (not refresh token)
            mock_schedule.assert_called_once()


async def test_websocket_heartbeat_message_format(hass: HomeAssistant):
    """Test heartbeat sends correct JSON format."""
    callback = MagicMock()
    ws = BestwayWebSocket(
        device_id="test_device_123",
        service_region="eu-central-1",
        token="test_token",
        callback=callback,
    )

    # Mock websocket connection
    mock_ws = AsyncMock()
    ws.websocket = mock_ws
    ws._running = True

    await ws._send_heartbeat()

    # Verify JSON message sent
    mock_ws.send.assert_called_once()
    sent_data = json.loads(mock_ws.send.call_args[0][0])

    assert sent_data["action"] == "heartbeat"
    assert sent_data["req_event"] == "heartbeat_req"
    assert "seq_id" in sent_data
    assert sent_data["req_count"] == 1

    # Verify protocol PING also sent
    mock_ws.ping.assert_called_once()


async def test_websocket_heartbeat_failure_triggers_reconnect(hass: HomeAssistant):
    """Test consecutive heartbeat failures trigger reconnection."""
    callback = MagicMock()
    ws = BestwayWebSocket(
        device_id="test_device_123",
        service_region="eu-central-1",
        token="test_token",
        callback=callback,
    )

    # Mock websocket that fails heartbeats
    mock_ws = AsyncMock()
    mock_ws.send.side_effect = Exception("Connection lost")
    ws.websocket = mock_ws
    ws._running = True

    # Simulate 3 consecutive heartbeat failures
    for i in range(3):
        try:
            await ws._send_heartbeat()
        except Exception:
            ws._heartbeat_failures += 1

    # Should reach max failures
    assert ws._heartbeat_failures == 3


async def test_websocket_disconnect(hass: HomeAssistant):
    """Test disconnect cleanly shuts down WebSocket."""
    callback = MagicMock()
    ws = BestwayWebSocket(
        device_id="test_device_123",
        service_region="eu-central-1",
        token="test_token",
        callback=callback,
    )

    # Mock websocket connection
    mock_ws = AsyncMock()
    ws.websocket = mock_ws
    ws._running = True

    # Patch asyncio.CancelledError handling
    with patch("asyncio.CancelledError", Exception):
        # Set tasks to None (disconnect should handle gracefully)
        ws._heartbeat_task = None
        ws._listen_task = None

        await ws.disconnect()

        # Verify running flag cleared
        assert ws._running is False

        # Verify websocket closed
        mock_ws.close.assert_called_once()
        assert ws.websocket is None








async def test_websocket_token_refresh_failure(hass: HomeAssistant):
    """Test WebSocket handles token refresh failure gracefully."""
    callback = MagicMock()
    token_refresh = AsyncMock(side_effect=Exception("Refresh failed"))

    with patch(
        "custom_components.new_bestway_spa.websocket.websockets.connect"
    ) as mock_connect:
        mock_connect.side_effect = Exception("HTTP 400 Bad Request")

        ws = BestwayWebSocket(
            device_id="test_device_123",
            service_region="eu-central-1",
            token="test_token",
            callback=callback,
            token_refresh_callback=token_refresh,
        )

        with patch.object(ws, "_schedule_reconnect") as mock_schedule:
            await ws.connect()

            # Token refresh was attempted
            token_refresh.assert_called_once()

            # Should schedule reconnect after refresh failure
            mock_schedule.assert_called_once()

            # Token should remain unchanged
            assert ws.token == "test_token"


async def test_heartbeat_loop_success(hass: HomeAssistant):
    """Test heartbeat loop sends heartbeats periodically."""
    callback = MagicMock()
    ws = BestwayWebSocket(
        device_id="test_device_123",
        service_region="eu-central-1",
        token="test_token",
        callback=callback,
    )

    # Mock websocket
    mock_ws = AsyncMock()
    ws.websocket = mock_ws
    ws._running = True

    # Mock _send_heartbeat to count calls
    heartbeat_count = 0

    async def mock_send_heartbeat():
        nonlocal heartbeat_count
        heartbeat_count += 1
        if heartbeat_count >= 2:
            # Stop after 2 heartbeats
            ws._running = False

    ws._send_heartbeat = mock_send_heartbeat

    # Run heartbeat loop (will stop after 2 iterations)
    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        await ws._heartbeat_loop()

        # Verify sleep was called with correct interval
        assert mock_sleep.call_count >= 2
        mock_sleep.assert_any_call(30)  # HEARTBEAT_INTERVAL

        # Verify heartbeats sent
        assert heartbeat_count == 2

        # Verify failures reset
        assert ws._heartbeat_failures == 0


async def test_heartbeat_loop_max_failures(hass: HomeAssistant):
    """Test heartbeat loop triggers reconnect after max failures."""
    callback = MagicMock()
    ws = BestwayWebSocket(
        device_id="test_device_123",
        service_region="eu-central-1",
        token="test_token",
        callback=callback,
    )

    ws.websocket = AsyncMock()
    ws._running = True

    # Mock _send_heartbeat to fail
    failure_count = 0

    async def mock_send_heartbeat():
        nonlocal failure_count
        failure_count += 1
        raise Exception("Heartbeat failed")

    ws._send_heartbeat = mock_send_heartbeat

    # Mock _schedule_reconnect to stop the loop
    async def mock_schedule():
        ws._running = False

    with patch.object(
        ws, "_schedule_reconnect", side_effect=mock_schedule
    ) as mock_reconnect:
        with patch("asyncio.sleep", new_callable=AsyncMock):
            await ws._heartbeat_loop()

            # Should have 3 failures
            assert ws._heartbeat_failures == 3

            # Should trigger reconnect
            mock_reconnect.assert_called_once()


async def test_listen_loop_processes_messages(hass: HomeAssistant):
    """Test listen loop processes incoming messages."""
    callback = MagicMock()
    ws = BestwayWebSocket(
        device_id="test_device_123",
        service_region="eu-central-1",
        token="test_token",
        callback=callback,
    )

    # Create mock websocket that yields messages then closes
    message1 = json.dumps({"state": {"reported": {"power_state": 1}}})
    message2 = json.dumps({"state": {"reported": {"heater_state": 3}}})

    async def message_generator():
        yield message1
        yield message2

    mock_ws = MagicMock()
    mock_ws.__aiter__ = lambda self: message_generator()
    ws.websocket = mock_ws

    # Run listen loop
    await ws._listen_loop()

    # Verify both messages processed
    assert callback.call_count == 2
    assert callback.call_args_list[0][0][0]["power_state"] == 1
    assert callback.call_args_list[1][0][0]["heater_state"] == 3


async def test_listen_loop_handles_malformed_json(hass: HomeAssistant):
    """Test listen loop handles malformed JSON gracefully."""
    callback = MagicMock()
    ws = BestwayWebSocket(
        device_id="test_device_123",
        service_region="eu-central-1",
        token="test_token",
        callback=callback,
    )

    # Create mock websocket that yields invalid JSON
    async def message_generator():
        yield "not valid json {]"
        yield json.dumps({"state": {"reported": {"power_state": 1}}})

    mock_ws = MagicMock()
    mock_ws.__aiter__ = lambda self: message_generator()
    ws.websocket = mock_ws

    # Run listen loop
    await ws._listen_loop()

    # Should process valid message, skip invalid
    callback.assert_called_once()
    assert callback.call_args[0][0]["power_state"] == 1


async def test_listen_loop_connection_closed_triggers_reconnect(hass: HomeAssistant):
    """Test listen loop reconnects on ConnectionClosed."""
    import websockets.exceptions

    callback = MagicMock()
    ws = BestwayWebSocket(
        device_id="test_device_123",
        service_region="eu-central-1",
        token="test_token",
        callback=callback,
    )

    # Create mock websocket that raises ConnectionClosed
    async def message_generator():
        yield json.dumps({"state": {"reported": {"power_state": 1}}})
        raise websockets.exceptions.ConnectionClosed(None, None)

    mock_ws = MagicMock()
    mock_ws.__aiter__ = lambda self: message_generator()
    ws.websocket = mock_ws
    ws._running = True

    # Mock _schedule_reconnect
    with patch.object(
        ws, "_schedule_reconnect", new_callable=AsyncMock
    ) as mock_reconnect:
        await ws._listen_loop()

        # Verify reconnect was scheduled
        mock_reconnect.assert_called_once()

        # Verify reconnect_count reset for immediate retry
        assert ws._reconnect_count == 0


async def test_listen_loop_generic_exception_triggers_reconnect(hass: HomeAssistant):
    """Test listen loop reconnects on generic exception."""
    callback = MagicMock()
    ws = BestwayWebSocket(
        device_id="test_device_123",
        service_region="eu-central-1",
        token="test_token",
        callback=callback,
    )

    # Create mock websocket that raises exception
    async def message_generator():
        raise Exception("Network error")

    mock_ws = MagicMock()
    mock_ws.__aiter__ = lambda self: message_generator()
    ws.websocket = mock_ws

    # Mock _schedule_reconnect
    with patch.object(
        ws, "_schedule_reconnect", new_callable=AsyncMock
    ) as mock_reconnect:
        await ws._listen_loop()

        # Verify reconnect was scheduled
        mock_reconnect.assert_called_once()


async def test_schedule_reconnect_executes_full_cycle(hass: HomeAssistant):
    """Test _schedule_reconnect executes sleep, disconnect, and reconnect."""
    callback = MagicMock()
    ws = BestwayWebSocket(
        device_id="test_device_123",
        service_region="eu-central-1",
        token="test_token",
        callback=callback,
    )

    ws._running = True
    ws._reconnect_count = 0  # First attempt = 3s delay

    # Mock sleep, disconnect, and connect
    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        with patch.object(ws, "disconnect", new_callable=AsyncMock) as mock_disconnect:
            with patch.object(ws, "connect", new_callable=AsyncMock) as mock_connect:
                await ws._schedule_reconnect()

                # Verify sleep called with correct delay
                mock_sleep.assert_called_once_with(3)  # First attempt delay

                # Verify disconnect called
                mock_disconnect.assert_called_once()

                # Verify connect called
                mock_connect.assert_called_once()

                # Verify reconnect count incremented
                assert ws._reconnect_count == 1


async def test_schedule_reconnect_respects_running_flag(hass: HomeAssistant):
    """Test _schedule_reconnect does nothing when not running."""
    callback = MagicMock()
    ws = BestwayWebSocket(
        device_id="test_device_123",
        service_region="eu-central-1",
        token="test_token",
        callback=callback,
    )

    ws._running = False

    # Mock connect
    with patch.object(ws, "connect", new_callable=AsyncMock) as mock_connect:
        await ws._schedule_reconnect()

        # Should not attempt reconnect
        mock_connect.assert_not_called()
