"""
Comprehensive unit tests for ReconnectionManager.

Tests reconnection logic with exponential backoff.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from media_service.sts.reconnection_manager import (
    ReconnectionManager,
    ReconnectionState,
)


class TestReconnectionState:
    """Tests for ReconnectionState dataclass."""

    def test_default_values(self) -> None:
        """Test default state values."""
        state = ReconnectionState()
        assert state.attempt == 0
        assert state.connected is False
        assert state.last_disconnect_time == 0.0
        assert state.total_reconnects == 0
        assert state.total_failures == 0

    def test_custom_values(self) -> None:
        """Test custom state values."""
        state = ReconnectionState(
            attempt=3,
            connected=True,
            total_reconnects=5,
        )
        assert state.attempt == 3
        assert state.connected is True
        assert state.total_reconnects == 5


class TestReconnectionManagerInit:
    """Tests for ReconnectionManager initialization."""

    def test_default_max_attempts(self) -> None:
        """Test default max attempts is 5."""
        manager = ReconnectionManager()
        assert manager.max_attempts == 5

    def test_custom_max_attempts(self) -> None:
        """Test custom max attempts."""
        manager = ReconnectionManager(max_attempts=10)
        assert manager.max_attempts == 10

    def test_unlimited_attempts(self) -> None:
        """Test unlimited attempts with 0."""
        manager = ReconnectionManager(max_attempts=0)
        assert manager.max_attempts == 0

    def test_default_initial_delay(self) -> None:
        """Test default initial delay is 1.0s."""
        manager = ReconnectionManager()
        assert manager.initial_delay == 1.0

    def test_custom_initial_delay(self) -> None:
        """Test custom initial delay."""
        manager = ReconnectionManager(initial_delay=2.0)
        assert manager.initial_delay == 2.0

    def test_default_max_delay(self) -> None:
        """Test default max delay is 30s."""
        manager = ReconnectionManager()
        assert manager.max_delay == 30.0

    def test_default_jitter(self) -> None:
        """Test default jitter is 0.1."""
        manager = ReconnectionManager()
        assert manager.jitter == 0.1

    def test_initial_state_not_connected(self) -> None:
        """Test initial state is not connected."""
        manager = ReconnectionManager()
        assert not manager.is_connected

    def test_initial_state_not_reconnecting(self) -> None:
        """Test initial state is not reconnecting."""
        manager = ReconnectionManager()
        assert not manager.is_reconnecting

    def test_initial_attempt_zero(self) -> None:
        """Test initial attempt is zero."""
        manager = ReconnectionManager()
        assert manager.current_attempt == 0


class TestReconnectionManagerCalculateDelay:
    """Tests for delay calculation."""

    def test_first_attempt_initial_delay(self) -> None:
        """Test first attempt uses initial delay."""
        manager = ReconnectionManager(initial_delay=1.0, jitter=0.0)
        delay = manager.calculate_delay(0)
        assert delay == 1.0

    def test_exponential_backoff(self) -> None:
        """Test exponential backoff doubles delay."""
        manager = ReconnectionManager(initial_delay=1.0, jitter=0.0)

        assert manager.calculate_delay(0) == 1.0
        assert manager.calculate_delay(1) == 2.0
        assert manager.calculate_delay(2) == 4.0
        assert manager.calculate_delay(3) == 8.0
        assert manager.calculate_delay(4) == 16.0

    def test_max_delay_cap(self) -> None:
        """Test delay is capped at max_delay."""
        manager = ReconnectionManager(initial_delay=1.0, max_delay=10.0, jitter=0.0)

        # 2^10 = 1024, should be capped at 10
        delay = manager.calculate_delay(10)
        assert delay == 10.0

    def test_jitter_adds_randomness(self) -> None:
        """Test jitter adds randomness to delay."""
        manager = ReconnectionManager(initial_delay=10.0, jitter=0.5)

        # Run multiple times to ensure randomness
        delays = [manager.calculate_delay(0) for _ in range(100)]

        # Delays should vary between 5 and 15 (10 +/- 50%)
        assert min(delays) < 10.0
        assert max(delays) > 10.0
        assert all(5.0 <= d <= 15.0 for d in delays)

    def test_zero_jitter(self) -> None:
        """Test zero jitter gives consistent delay."""
        manager = ReconnectionManager(initial_delay=5.0, jitter=0.0)

        delays = [manager.calculate_delay(0) for _ in range(10)]

        # All delays should be exactly 5.0
        assert all(d == 5.0 for d in delays)


class TestReconnectionManagerOnConnected:
    """Tests for on_connected behavior."""

    def test_sets_connected_flag(self) -> None:
        """Test on_connected sets connected flag."""
        manager = ReconnectionManager()
        manager.on_connected()

        assert manager.is_connected

    def test_resets_attempt_counter(self) -> None:
        """Test on_connected resets attempt counter."""
        manager = ReconnectionManager()
        manager.state.attempt = 5

        manager.on_connected()

        assert manager.current_attempt == 0

    def test_increments_reconnect_count_when_not_connected(self) -> None:
        """Test on_connected increments reconnect count when not connected."""
        manager = ReconnectionManager()
        assert manager.state.total_reconnects == 0

        manager.on_connected()
        assert manager.state.total_reconnects == 1

    def test_does_not_increment_when_already_connected(self) -> None:
        """Test on_connected doesn't increment if already connected."""
        manager = ReconnectionManager()
        manager.state.connected = True
        manager.state.total_reconnects = 5

        manager.on_connected()

        assert manager.state.total_reconnects == 5


class TestReconnectionManagerOnDisconnected:
    """Tests for on_disconnected behavior."""

    def test_clears_connected_flag(self) -> None:
        """Test on_disconnected clears connected flag."""
        manager = ReconnectionManager()
        manager.state.connected = True

        manager.on_disconnected()

        assert not manager.is_connected

    def test_sets_disconnect_time(self) -> None:
        """Test on_disconnected sets disconnect time."""
        manager = ReconnectionManager()

        with patch("time.time", return_value=12345.0):
            manager.on_disconnected()

        assert manager.state.last_disconnect_time == 12345.0


class TestReconnectionManagerReconnectLoop:
    """Tests for reconnection loop."""

    @pytest.mark.asyncio
    async def test_reconnect_loop_calls_callback(self) -> None:
        """Test reconnect loop calls callback."""
        manager = ReconnectionManager(initial_delay=0.01, max_attempts=1)
        callback = AsyncMock(return_value=True)
        manager.set_reconnect_callback(callback)

        await manager.trigger_reconnect()
        await asyncio.sleep(0.05)

        callback.assert_called()

    @pytest.mark.asyncio
    async def test_reconnect_loop_stops_on_success(self) -> None:
        """Test reconnect loop stops when callback returns True."""
        manager = ReconnectionManager(initial_delay=0.01)
        callback = AsyncMock(return_value=True)
        manager.set_reconnect_callback(callback)

        await manager.trigger_reconnect()
        await asyncio.sleep(0.05)

        assert manager.is_connected
        assert not manager.is_reconnecting

    @pytest.mark.asyncio
    async def test_reconnect_loop_retries_on_failure(self) -> None:
        """Test reconnect loop retries when callback returns False."""
        manager = ReconnectionManager(initial_delay=0.01, max_attempts=3)
        call_count = 0

        async def failing_callback():
            nonlocal call_count
            call_count += 1
            return call_count >= 2  # Succeed on second attempt

        manager.set_reconnect_callback(failing_callback)

        await manager.trigger_reconnect()
        await asyncio.sleep(0.1)

        assert call_count == 2
        assert manager.is_connected

    @pytest.mark.asyncio
    async def test_reconnect_loop_stops_at_max_attempts(self) -> None:
        """Test reconnect loop stops after max attempts."""
        manager = ReconnectionManager(initial_delay=0.01, max_attempts=3)
        callback = AsyncMock(return_value=False)
        manager.set_reconnect_callback(callback)

        await manager.trigger_reconnect()
        await asyncio.sleep(0.2)

        assert callback.call_count == 3
        assert not manager.is_connected
        assert manager.state.total_failures == 1


class TestReconnectionManagerTriggerReconnect:
    """Tests for trigger_reconnect."""

    @pytest.mark.asyncio
    async def test_trigger_reconnect_returns_true(self) -> None:
        """Test trigger_reconnect returns True when started."""
        manager = ReconnectionManager(initial_delay=0.1)
        callback = AsyncMock(return_value=True)
        manager.set_reconnect_callback(callback)

        result = await manager.trigger_reconnect()

        assert result is True
        manager.stop()

    @pytest.mark.asyncio
    async def test_trigger_reconnect_returns_false_if_already_reconnecting(self) -> None:
        """Test trigger_reconnect returns False if already in progress."""
        manager = ReconnectionManager(initial_delay=1.0)
        callback = AsyncMock(return_value=False)
        manager.set_reconnect_callback(callback)

        await manager.trigger_reconnect()
        result = await manager.trigger_reconnect()

        assert result is False
        manager.stop()

    @pytest.mark.asyncio
    async def test_trigger_reconnect_returns_false_without_callback(self) -> None:
        """Test trigger_reconnect returns False without callback."""
        manager = ReconnectionManager()

        result = await manager.trigger_reconnect()

        assert result is False


class TestReconnectionManagerStop:
    """Tests for stop functionality."""

    @pytest.mark.asyncio
    async def test_stop_cancels_reconnect_task(self) -> None:
        """Test stop cancels ongoing reconnection."""
        manager = ReconnectionManager(initial_delay=10.0)
        callback = AsyncMock(return_value=False)
        manager.set_reconnect_callback(callback)

        await manager.trigger_reconnect()
        assert manager.is_reconnecting

        manager.stop()
        await asyncio.sleep(0.01)

        assert not manager.is_reconnecting

    def test_stop_when_not_reconnecting(self) -> None:
        """Test stop is no-op when not reconnecting."""
        manager = ReconnectionManager()

        # Should not raise
        manager.stop()


class TestReconnectionManagerReset:
    """Tests for reset functionality."""

    def test_reset_clears_attempt(self) -> None:
        """Test reset clears attempt counter."""
        manager = ReconnectionManager()
        manager.state.attempt = 5

        manager.reset()

        assert manager.current_attempt == 0

    def test_reset_clears_connected(self) -> None:
        """Test reset clears connected flag."""
        manager = ReconnectionManager()
        manager.state.connected = True

        manager.reset()

        assert not manager.is_connected

    @pytest.mark.asyncio
    async def test_reset_stops_reconnection(self) -> None:
        """Test reset stops ongoing reconnection."""
        manager = ReconnectionManager(initial_delay=10.0)
        callback = AsyncMock(return_value=False)
        manager.set_reconnect_callback(callback)

        await manager.trigger_reconnect()
        manager.reset()
        await asyncio.sleep(0.01)

        assert not manager.is_reconnecting


class TestReconnectionManagerCallbackSetter:
    """Tests for callback setter."""

    def test_set_reconnect_callback(self) -> None:
        """Test setting reconnect callback."""
        manager = ReconnectionManager()
        callback = AsyncMock()

        manager.set_reconnect_callback(callback)

        assert manager._reconnect_callback is callback
