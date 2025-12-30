"""
Unit tests for BackpressureHandler class.

Tests T053-T055 from tasks.md - validating backpressure handling.
"""

from __future__ import annotations

import asyncio

import pytest

from media_service.sts.backpressure_handler import BackpressureHandler
from media_service.sts.models import BackpressurePayload


class TestBackpressureHandlerInit:
    """Tests for BackpressureHandler initialization."""

    def test_default_values(self) -> None:
        """Test default handler values."""
        handler = BackpressureHandler()

        assert handler.is_paused is False
        assert handler.current_delay_ms == 0
        assert handler.state.current_severity == "none"


class TestBackpressureHandlerSlowDown:
    """Tests for slow_down action handling."""

    @pytest.mark.asyncio
    async def test_slow_down_sets_delay(self) -> None:
        """Test slow_down action sets delay."""
        handler = BackpressureHandler()

        payload = BackpressurePayload(
            stream_id="test",
            severity="medium",
            current_inflight=3,
            queue_depth=10,
            action="slow_down",
            recommended_delay_ms=500,
        )

        await handler.handle(payload)

        assert handler.current_delay_ms == 500
        assert handler.is_paused is False
        assert handler.total_slow_downs == 1

    @pytest.mark.asyncio
    async def test_slow_down_uses_default_for_severity(self) -> None:
        """Test slow_down uses default delay when not specified."""
        handler = BackpressureHandler()

        payload = BackpressurePayload(
            stream_id="test",
            severity="high",
            current_inflight=5,
            queue_depth=20,
            action="slow_down",
            recommended_delay_ms=0,  # Not specified
        )

        await handler.handle(payload)

        # Should use default for "high" severity (1000ms)
        assert handler.current_delay_ms == 1000


class TestBackpressureHandlerPause:
    """Tests for pause action handling."""

    @pytest.mark.asyncio
    async def test_pause_blocks_requests(self) -> None:
        """Test pause action sets is_paused."""
        handler = BackpressureHandler()

        payload = BackpressurePayload(
            stream_id="test",
            severity="high",
            current_inflight=5,
            queue_depth=20,
            action="pause",
        )

        await handler.handle(payload)

        assert handler.is_paused is True
        assert handler.total_pauses == 1

    @pytest.mark.asyncio
    async def test_wait_if_paused_blocks(self) -> None:
        """Test wait_if_paused blocks when paused."""
        handler = BackpressureHandler()

        # Pause
        payload = BackpressurePayload(
            stream_id="test",
            severity="high",
            current_inflight=5,
            queue_depth=20,
            action="pause",
        )
        await handler.handle(payload)

        # Should timeout because we're paused
        result = await handler.wait_if_paused(timeout=0.1)

        assert result is False  # Timeout


class TestBackpressureHandlerResume:
    """Tests for resume (none action) handling."""

    @pytest.mark.asyncio
    async def test_resume_unblocks(self) -> None:
        """Test resume action clears pause state."""
        handler = BackpressureHandler()

        # First pause
        pause_payload = BackpressurePayload(
            stream_id="test",
            severity="high",
            current_inflight=5,
            queue_depth=20,
            action="pause",
        )
        await handler.handle(pause_payload)
        assert handler.is_paused is True

        # Then resume
        resume_payload = BackpressurePayload(
            stream_id="test",
            severity="low",
            current_inflight=1,
            queue_depth=0,
            action="none",
        )
        await handler.handle(resume_payload)

        assert handler.is_paused is False
        assert handler.current_delay_ms == 0
        assert handler.state.current_severity == "none"

    @pytest.mark.asyncio
    async def test_wait_if_paused_returns_true_after_resume(self) -> None:
        """Test wait_if_paused returns True after resume."""
        handler = BackpressureHandler()

        # Start paused
        pause_payload = BackpressurePayload(
            stream_id="test",
            severity="high",
            current_inflight=5,
            queue_depth=20,
            action="pause",
        )
        await handler.handle(pause_payload)

        # Resume in a background task
        async def resume_soon():
            await asyncio.sleep(0.05)
            resume_payload = BackpressurePayload(
                stream_id="test",
                severity="low",
                current_inflight=0,
                queue_depth=0,
                action="none",
            )
            await handler.handle(resume_payload)

        asyncio.create_task(resume_soon())

        # Wait should succeed after resume
        result = await handler.wait_if_paused(timeout=0.5)

        assert result is True


class TestBackpressureHandlerApplyDelay:
    """Tests for apply_delay method."""

    @pytest.mark.asyncio
    async def test_apply_delay_sleeps(self) -> None:
        """Test apply_delay sleeps for delay_ms."""
        handler = BackpressureHandler()
        handler.state.delay_ms = 100  # 100ms delay

        import time

        start = time.monotonic()
        await handler.apply_delay()
        elapsed = (time.monotonic() - start) * 1000

        assert elapsed >= 90  # Allow some tolerance
        assert elapsed < 200

    @pytest.mark.asyncio
    async def test_apply_delay_no_sleep_when_zero(self) -> None:
        """Test apply_delay doesn't sleep when delay is 0."""
        handler = BackpressureHandler()

        import time

        start = time.monotonic()
        await handler.apply_delay()
        elapsed = (time.monotonic() - start) * 1000

        assert elapsed < 10  # Should be almost instant


class TestBackpressureHandlerWaitAndDelay:
    """Tests for wait_and_delay combined method."""

    @pytest.mark.asyncio
    async def test_wait_and_delay_when_not_paused(self) -> None:
        """Test wait_and_delay with no backpressure."""
        handler = BackpressureHandler()

        result = await handler.wait_and_delay()

        assert result is True

    @pytest.mark.asyncio
    async def test_wait_and_delay_applies_delay(self) -> None:
        """Test wait_and_delay applies slow_down delay."""
        handler = BackpressureHandler()
        handler.state.delay_ms = 50

        import time

        start = time.monotonic()
        result = await handler.wait_and_delay()
        elapsed = (time.monotonic() - start) * 1000

        assert result is True
        assert elapsed >= 40  # Should have slept


class TestBackpressureHandlerReset:
    """Tests for reset method."""

    @pytest.mark.asyncio
    async def test_reset_clears_state(self) -> None:
        """Test reset clears all state."""
        handler = BackpressureHandler()

        # Set some state
        handler.state.is_paused = True
        handler.state.delay_ms = 500
        handler.state.current_severity = "high"

        handler.reset()

        assert handler.is_paused is False
        assert handler.current_delay_ms == 0
        assert handler.state.current_severity == "none"
